"""Score a trained model against the baseline on an arbitrary window.

This is for post-training health checks — drift monitoring, A/B comparing
two booster files, or sanity-checking after a deploy. Training already
prints the launch-day metrics in :mod:`forecaster.train`.

Run from the api venv:

    cd api && .venv/bin/python -m forecaster.evaluate \\
        --horizon 120 --days 1
"""

from __future__ import annotations

import argparse
import json
import sys
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
from forecaster.train import MODEL_DIR

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mae(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.mean(np.abs(y_true.values - y_pred.values)))


def _prepare_x(frame: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Same shape transformation as in training so predict works."""
    x = frame[feature_columns(config)].copy()
    x["station_id"] = x["station_id"].astype("category")
    return x


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate(
    session: "Session",
    start: datetime,
    end: datetime,
    horizon_minutes: int = 120,
    model_path: Path | str | None = None,
    baseline_train_days: int = 3,
) -> dict:
    """Score the model on ``[start, end)``. Comparison MAE against baseline.

    Args:
        start, end:           UTC window to score (exclusive end).
        horizon_minutes:      must match what the model was trained on.
        model_path:           default ``MODEL_DIR / forecast_<H>m.lgb``.
        baseline_train_days:  baseline (hour-of-week mean) is fitted on the
                              N days immediately before ``start``, never
                              overlapping the eval window.

    Returns:
        Dict with ``model_mae``, ``baseline_mae``, ``n_samples``,
        ``win_pct``, ``mae_by_hour`` (Series), ``residual_p95``.
    """
    cfg = FeatureConfig(horizon_minutes=horizon_minutes)
    path = Path(model_path) if model_path else MODEL_DIR / f"forecast_{horizon_minutes}m.lgb"
    if not path.exists():
        raise FileNotFoundError(f"booster not found at {path}")
    booster = lgb.Booster(model_file=str(path))

    # --- Build the eval frame ---------------------------------------------
    frame = build_training_frame(session, start, end, cfg)
    if frame.empty:
        return {
            "model_mae": None,
            "baseline_mae": None,
            "n_samples": 0,
            "win_pct": None,
            "model_path": str(path),
            "window": [start.isoformat(), end.isoformat()],
        }

    y_true = frame["target"].astype("float32")
    X = _prepare_x(frame, cfg)
    y_pred_model = pd.Series(booster.predict(X), index=X.index)

    # --- Baseline trained on history before the eval window --------------
    baseline_start = start - timedelta(days=baseline_train_days)
    baseline_table = train_baseline(session, baseline_start, start)
    target_ts = pd.to_datetime(frame["ts"], utc=True) + timedelta(minutes=horizon_minutes)
    pred_input = pd.DataFrame(
        {"station_id": frame["station_id"].values, "target_ts": target_ts.values},
        index=frame.index,
    )
    y_pred_base = predict_baseline_batch(baseline_table, pred_input)

    # --- Metrics ----------------------------------------------------------
    model_err = (y_true - y_pred_model).abs()
    base_err = (y_true - y_pred_base).abs()
    residual_p95 = float(model_err.quantile(0.95))
    mae_by_hour = (
        pd.DataFrame({"hour": frame["hour"].values, "err": model_err.values})
        .groupby("hour")["err"]
        .mean()
        .astype("float32")
    )

    return {
        "model_mae": _mae(y_true, y_pred_model),
        "baseline_mae": _mae(y_true, y_pred_base),
        "n_samples": int(len(y_true)),
        "win_pct": float((model_err < base_err).mean()),
        "residual_p95": residual_p95,
        "mae_by_hour": {int(k): float(v) for k, v in mae_by_hour.items()},
        "model_path": str(path),
        "window": [start.isoformat(), end.isoformat()],
        "horizon_minutes": horizon_minutes,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the forecaster on a window")
    parser.add_argument(
        "--horizon", type=int, default=120, help="minutes ahead (must match training)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="evaluate the most recent N full days (anchored on MAX(ts))",
    )
    args = parser.parse_args()

    from db.session import SessionLocal

    with SessionLocal() as session:
        end_ts = session.execute(text("SELECT MAX(ts) FROM status_snapshots")).scalar_one()
        if end_ts is None:
            print("status_snapshots is empty", file=sys.stderr)
            return 1
        end = end_ts.astimezone(timezone.utc)
        start = end - timedelta(days=args.days)
        result = evaluate(session, start, end, horizon_minutes=args.horizon)

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
