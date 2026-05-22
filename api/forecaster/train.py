"""Train the LightGBM forecaster and persist its booster.

The training script is the orchestrator: it pulls features, builds the
hour-of-week baseline as a benchmark, fits LightGBM on a strict
chronological split, and writes both the model file and a row in
``model_runs`` so we can compare runs over time.

Run from the api venv:

    cd api && .venv/bin/python -m forecaster.train [--horizon 120]

or programmatically from a cron handler in ``main.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy import text

from forecaster.baseline import predict_baseline_batch, train_baseline
from forecaster.features import (
    FeatureConfig,
    build_training_frame,
    feature_columns,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"

CATEGORICAL_FEATURES = ["station_id", "dow", "hour", "is_weekend"]


# ---------------------------------------------------------------------------
# Split computation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Split:
    """Holds the boundaries of a chronological train/val/test split.

    All timestamps are UTC. Conventions: ``[train_start, train_end)``,
    ``[train_end, val_end)``, ``[val_end, test_end)``.
    """

    train_start: datetime
    train_end: datetime
    val_end: datetime
    test_end: datetime

    @property
    def days_total(self) -> float:
        return (self.test_end - self.train_start).total_seconds() / 86400.0


def auto_split(
    session: "Session",
    train_days: int = 3,
    val_days: int = 1,
    test_days: int = 1,
) -> Split:
    """Pick the split based on the actual data window.

    Anchored on ``MAX(ts)`` so we always train on the freshest data and test
    on the most recent day, which is what production cares about.
    """
    end_ts = session.execute(text("SELECT MAX(ts) FROM status_snapshots")).scalar_one()
    if end_ts is None:
        raise RuntimeError("status_snapshots is empty — nothing to train on")
    test_end = end_ts.astimezone(timezone.utc)
    val_end = test_end - timedelta(days=test_days)
    train_end = val_end - timedelta(days=val_days)
    train_start = train_end - timedelta(days=train_days)
    return Split(train_start, train_end, val_end, test_end)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _mae(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.mean(np.abs(y_true.values - y_pred.values)))


def _win_pct(
    y_true: pd.Series,
    y_pred_model: pd.Series,
    y_pred_baseline: pd.Series,
) -> float:
    """% of rows where the model's absolute error beats the baseline's.

    Equal-error rows count as a baseline win — we're strict.
    """
    model_err = (y_true - y_pred_model).abs()
    base_err = (y_true - y_pred_baseline).abs()
    return float((model_err < base_err).mean())


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def _prepare_xy(
    frame: pd.DataFrame,
    config: FeatureConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    """Split features from target. Cast station_id to a category code."""
    features = frame[feature_columns(config)].copy()
    # LightGBM accepts a pandas Categorical directly; using .codes loses the
    # mapping. We keep it as category so booster.feature_name_ stays readable.
    features["station_id"] = features["station_id"].astype("category")
    target = frame["target"].astype("float32")
    return features, target


def train(
    session: "Session",
    horizon_minutes: int = 120,
    config: FeatureConfig | None = None,
    split: Split | None = None,
    num_boost_round: int = 1500,
    early_stopping_rounds: int = 75,
) -> dict:
    """Fit LightGBM, evaluate, persist. Returns the metrics dict.

    Side effects: writes ``forecast_<horizon>m.lgb`` under ``MODEL_DIR`` and
    inserts a row in ``model_runs``.
    """
    cfg = config or FeatureConfig(horizon_minutes=horizon_minutes)
    split = split or auto_split(session)

    print(f"[train] split: {split}", file=sys.stderr)

    # ---- Build the training frame in one go (cheap to slice afterwards) --
    started = time.monotonic()
    frame = build_training_frame(session, split.train_start, split.test_end, cfg)
    if frame.empty:
        raise RuntimeError("build_training_frame returned no rows — bad window?")
    print(
        f"[train] frame built in {time.monotonic() - started:.1f}s — "
        f"{len(frame):,} rows, {frame['station_id'].nunique()} stations",
        file=sys.stderr,
    )

    ts = pd.to_datetime(frame["ts"], utc=True)
    train_mask = (ts >= pd.Timestamp(split.train_start)) & (ts < pd.Timestamp(split.train_end))
    val_mask   = (ts >= pd.Timestamp(split.train_end))   & (ts < pd.Timestamp(split.val_end))
    test_mask  = (ts >= pd.Timestamp(split.val_end))     & (ts < pd.Timestamp(split.test_end))

    X, y = _prepare_xy(frame, cfg)
    X_train, y_train = X.loc[train_mask], y.loc[train_mask]
    X_val,   y_val   = X.loc[val_mask],   y.loc[val_mask]
    X_test,  y_test  = X.loc[test_mask],  y.loc[test_mask]

    print(
        f"[train] sizes train={len(X_train):,} val={len(X_val):,} test={len(X_test):,}",
        file=sys.stderr,
    )

    # ---- Hour-of-week baseline as benchmark ------------------------------
    baseline_table = train_baseline(session, split.train_start, split.train_end)
    test_with_ts = frame.loc[test_mask, ["station_id", "ts"]].rename(
        columns={"ts": "target_ts"}
    )
    # The "target ts" is t + horizon; baseline is keyed by that future hour.
    test_with_ts["target_ts"] = test_with_ts["target_ts"] + timedelta(
        minutes=cfg.horizon_minutes
    )
    y_test_baseline = predict_baseline_batch(baseline_table, test_with_ts)

    # ---- Fit LightGBM (native API; no sklearn dep) -----------------------
    train_data = lgb.Dataset(
        X_train, label=y_train, categorical_feature=CATEGORICAL_FEATURES
    )
    val_data = lgb.Dataset(
        X_val, label=y_val, categorical_feature=CATEGORICAL_FEATURES, reference=train_data
    )
    params = {
        "objective": "regression_l1",
        "metric": "mae",
        "learning_rate": 0.05,
        "num_leaves": 64,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.9,
        "verbose": -1,
        "seed": 42,
    }
    fit_started = time.monotonic()
    booster = lgb.train(
        params,
        train_data,
        num_boost_round=num_boost_round,
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
        callbacks=[
            lgb.early_stopping(early_stopping_rounds),
            lgb.log_evaluation(100),
        ],
    )
    fit_seconds = time.monotonic() - fit_started
    print(
        f"[train] fit done in {fit_seconds:.1f}s — best iter {booster.best_iteration}",
        file=sys.stderr,
    )

    # ---- Test metrics ----------------------------------------------------
    y_pred_test = pd.Series(booster.predict(X_test), index=X_test.index)
    mae_val  = _mae(y_val,  pd.Series(booster.predict(X_val), index=X_val.index))
    mae_test = _mae(y_test, y_pred_test)
    mae_baseline = _mae(y_test, y_test_baseline)
    win_pct = _win_pct(y_test, y_pred_test, y_test_baseline)

    print(
        f"[train] MAE val={mae_val:.4f} test={mae_test:.4f} "
        f"baseline={mae_baseline:.4f} win_pct={win_pct:.1%}",
        file=sys.stderr,
    )

    # ---- Persist booster -------------------------------------------------
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_version = f"v1_{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    model_path = MODEL_DIR / f"forecast_{cfg.horizon_minutes}m.lgb"
    booster.save_model(str(model_path))
    print(f"[train] saved {model_path}", file=sys.stderr)

    # ---- Log to model_runs ----------------------------------------------
    metrics = {
        "horizon_minutes": cfg.horizon_minutes,
        "mae_val": mae_val,
        "mae_test": mae_test,
        "baseline_mae_test": mae_baseline,
        "win_pct": win_pct,
        "best_iteration": int(booster.best_iteration or 0),
        "fit_seconds": round(fit_seconds, 2),
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_test)),
        "train_start": split.train_start.isoformat(),
        "train_end": split.train_end.isoformat(),
        "test_end": split.test_end.isoformat(),
    }

    session.execute(
        text(
            """
            INSERT INTO model_runs (model_version, feature_list, metrics, notes)
            VALUES (:v, :feats, :metrics, :notes)
            """
        ),
        {
            "v": model_version,
            "feats": feature_columns(cfg),
            "metrics": json.dumps(metrics),
            "notes": f"LightGBM v1, horizon={cfg.horizon_minutes}m",
        },
    )
    session.commit()
    print(f"[train] logged model_runs row for {model_version}", file=sys.stderr)

    return {**metrics, "model_version": model_version, "model_path": str(model_path)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    parser = argparse.ArgumentParser(description="Train the Vélib Wizard forecaster")
    parser.add_argument("--horizon", type=int, default=120, help="minutes ahead (default 120)")
    args = parser.parse_args()

    from db.session import SessionLocal

    with SessionLocal() as session:
        result = train(session, horizon_minutes=args.horizon)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
