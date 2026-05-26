"""Live inference: load the trained booster and refresh per-station forecasts.

The booster is loaded lazily on first use and cached in the process. A
nightly cron retrains and writes a new model file; calling
:func:`reset_booster_cache` from the training handler flips the cache so
the next inference picks up the fresh weights.

LightGBM persists the categorical mapping (``pandas_categorical``) inside
the booster file when training was given pandas Categorical columns, so
we don't need a sidecar to recover the ``station_id`` codes at inference.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy import text

from forecaster.features import (
    FeatureConfig,
    build_inference_frame,
    feature_columns,
)
from forecaster.train import MODEL_DIR

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# In-process LRU. Keys are horizon (minutes). Mutated by reset_booster_cache
# after a retrain.
_booster_cache: dict[int, lgb.Booster] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_booster(horizon_minutes: int) -> lgb.Booster:
    """Return the booster for ``horizon_minutes``, loading from disk once."""
    if horizon_minutes in _booster_cache:
        return _booster_cache[horizon_minutes]
    path = MODEL_DIR / f"forecast_{horizon_minutes}m.lgb"
    if not path.exists():
        raise FileNotFoundError(
            f"booster not found at {path} — has train.py been run?"
        )
    booster = lgb.Booster(model_file=str(path))
    _booster_cache[horizon_minutes] = booster
    return booster


def reset_booster_cache(horizon_minutes: int | None = None) -> None:
    """Drop cached boosters so the next call reloads from disk.

    Call this from the training handler right after a successful retrain.
    """
    if horizon_minutes is None:
        _booster_cache.clear()
    else:
        _booster_cache.pop(horizon_minutes, None)


def _compute_risks(bikes_pct: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Soft thresholds → ``risk_bike`` and ``risk_dock`` in [0, 1].

    Linear ramp:
      * ``risk_bike`` rises from 0 at 85% full to 1 at 95% full.
      * ``risk_dock`` rises from 0 at 15% full to 1 at 5% full.

    Both saturate at 1 outside their ramp. The shape was chosen so the
    map's red/yellow/green coloring gets a useful gradient near the
    interesting thresholds without being a hard step.
    """
    risk_bike = ((bikes_pct - 0.85) / 0.10).clip(0.0, 1.0).astype("float32")
    risk_dock = ((0.15 - bikes_pct) / 0.10).clip(0.0, 1.0).astype("float32")
    return risk_bike, risk_dock


def _align_station_categories(
    frame: pd.DataFrame, booster: lgb.Booster
) -> pd.DataFrame:
    """Recover the categorical mapping the booster was trained on.

    LightGBM stores ``pandas_categorical`` (a list, one entry per
    categorical column) when the training DataFrame had Categorical
    dtypes. We re-apply the same categories so station_ids map to the
    same internal codes the model expects.
    """
    pc = getattr(booster, "pandas_categorical", None)
    if not pc:
        frame["station_id"] = frame["station_id"].astype("category")
        return frame
    # Order matches the CATEGORICAL_FEATURES list in train.py:
    # ['station_id', 'dow', 'hour', 'is_weekend']. We only need to align
    # station_id — the others are integers and always cast identically.
    station_cats = pc[0]
    frame["station_id"] = pd.Categorical(
        frame["station_id"], categories=station_cats
    )
    return frame


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_UPSERT_SQL = """
INSERT INTO forecasts (
    station_id, horizon_minutes, risk_bike, risk_dock,
    predicted_pct, model_version
)
VALUES (:sid, :h, :rb, :rd, :pp, :v)
ON CONFLICT (station_id, horizon_minutes, model_version)
DO UPDATE SET
    risk_bike     = EXCLUDED.risk_bike,
    risk_dock     = EXCLUDED.risk_dock,
    predicted_pct = EXCLUDED.predicted_pct,
    computed_at   = now()
"""


def refresh_forecasts(
    session: "Session",
    horizon_minutes: int = 120,
    model_version: str | None = None,
) -> dict:
    """Batch-predict every station and upsert the result into ``forecasts``.

    Args:
        horizon_minutes:  must match a trained model on disk.
        model_version:    PK component for the upsert. Defaults to the
                          latest entry in ``model_runs``.

    Returns: summary dict with ``n_stations`` and aggregate stats.
    """
    cfg = FeatureConfig(horizon_minutes=horizon_minutes)
    booster = _load_booster(horizon_minutes)

    if model_version is None:
        row = session.execute(
            text("SELECT model_version FROM model_runs ORDER BY trained_at DESC LIMIT 1")
        ).first()
        if row is None:
            raise RuntimeError(
                "no model_runs entries — call train_forecast first"
            )
        model_version = row[0]

    now = datetime.now(tz=timezone.utc)
    # Diagnostic: when the inference frame ends up empty we want to know
    # whether _load_raw returned nothing (DB / connection issue) or whether
    # dropna stripped everything (lag/feature alignment issue).
    from forecaster.features import _load_raw

    pad = timedelta(minutes=max(cfg.lag_minutes) + cfg.grid_minutes)
    raw_for_count = _load_raw(session, now - pad, now + timedelta(minutes=1))
    raw_rows = int(len(raw_for_count))
    raw_stations = int(raw_for_count["station_id"].nunique()) if raw_rows else 0
    del raw_for_count  # don't double the memory

    frame = build_inference_frame(session, now, cfg)
    if frame.empty:
        logger.warning(
            "inference frame empty — skipping upsert (raw_rows=%d, raw_stations=%d, window=%dm)",
            raw_rows,
            raw_stations,
            pad.total_seconds() / 60,
        )
        return {
            "n_stations": 0,
            "raw_rows": raw_rows,
            "raw_stations": raw_stations,
            "window_minutes": int(pad.total_seconds() / 60),
            "model_version": model_version,
            "computed_at": now.isoformat(),
        }

    frame = _align_station_categories(frame, booster)
    X = frame[feature_columns(cfg)]
    predictions = pd.Series(booster.predict(X), index=X.index).clip(0.0, 1.0)
    risk_bike, risk_dock = _compute_risks(predictions)

    payload = [
        {
            "sid": str(sid),
            "h": horizon_minutes,
            "rb": float(rb),
            "rd": float(rd),
            "pp": float(pp),
            "v": model_version,
        }
        for sid, rb, rd, pp in zip(
            frame["station_id"].astype(str),
            risk_bike,
            risk_dock,
            predictions,
            strict=True,
        )
    ]
    session.execute(text(_UPSERT_SQL), payload)
    session.commit()

    return {
        "n_stations": len(payload),
        "model_version": model_version,
        "computed_at": now.isoformat(),
        "mean_predicted_pct": float(predictions.mean()),
        "mean_risk_bike": float(risk_bike.mean()),
        "mean_risk_dock": float(risk_dock.mean()),
    }


def predict_one(
    session: "Session",
    station_id: str,
    horizon_minutes: int = 120,
) -> dict | None:
    """Return the latest stored forecast for one station, or None."""
    row = session.execute(
        text(
            """
            SELECT risk_bike, risk_dock, predicted_pct, model_version, computed_at
            FROM forecasts
            WHERE station_id = :sid AND horizon_minutes = :h
            ORDER BY computed_at DESC
            LIMIT 1
            """
        ),
        {"sid": station_id, "h": horizon_minutes},
    ).mappings().first()
    if row is None:
        return None
    return {
        "station_id": station_id,
        "horizon_minutes": horizon_minutes,
        "risk_bike": float(row["risk_bike"]),
        "risk_dock": float(row["risk_dock"]),
        "predicted_pct": (
            float(row["predicted_pct"]) if row["predicted_pct"] is not None else None
        ),
        "model_version": row["model_version"],
        "computed_at": row["computed_at"].isoformat(),
    }
