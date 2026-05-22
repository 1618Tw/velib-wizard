"""Build the feature frames used by the forecaster.

Two public entry points:

* :func:`build_training_frame` — historical window with target column,
  consumed by ``baseline.py`` and ``train.py``.
* :func:`build_inference_frame` — one row per station as of ``now``,
  consumed by ``predict.py`` to produce live forecasts.

Both go through the same pipeline so train- and inference-time features are
identical (no train/serve skew).

Configuration: see :class:`FeatureConfig`. For v1 we encode only the inputs we
can actually compute reliably from 5 days of data — no weather (collector not
running yet), no "same hour last week" (would need 7+ days), no FR holiday
flag (punted to v2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureConfig:
    """Knobs for the feature pipeline.

    Attributes:
        horizon_minutes:   how far ahead the target lives (default 2h).
        lag_minutes:       which lags to add as features. Must be multiples
                           of ``GRID_MINUTES``.
        rolling_minutes:   trailing window size for the rolling-mean feature.
        grid_minutes:      resample resolution. The collector polls every
                           5 minutes; keeping the same grid makes lags trivial.
    """

    horizon_minutes: int = 120
    lag_minutes: tuple[int, ...] = (15, 30, 60, 180)
    rolling_minutes: int = 60
    grid_minutes: int = 5


# Columns the pipeline produces. Exposed so callers (train.py) can pin the
# feature list explicitly and store it in ``model_runs.feature_list``.
def feature_columns(config: FeatureConfig) -> list[str]:
    """The ordered feature list that ``build_*_frame`` will emit."""
    lag_cols = [f"bikes_pct_lag_{m}m" for m in config.lag_minutes]
    return [
        # Station identity / geometry
        "station_id",
        "lat",
        "lon",
        "capacity",
        # Temporal
        "hour",
        "dow",
        "is_weekend",
        "hour_sin",
        "hour_cos",
        # State now
        "bikes_pct",
        *lag_cols,
        "bikes_pct_roll_1h",
        "bikes_pct_delta_15m",
    ]


# ---------------------------------------------------------------------------
# DB I/O
# ---------------------------------------------------------------------------


_RAW_SQL = """
SELECT
    ss.station_id,
    ss.ts,
    ss.bikes,
    ss.docks,
    s.capacity,
    s.lat,
    s.lon
FROM status_snapshots ss
JOIN stations s ON s.station_id = ss.station_id
WHERE ss.ts >= :start AND ss.ts < :end
ORDER BY ss.station_id, ss.ts
"""


def _load_raw(session: "Session", start: datetime, end: datetime) -> pd.DataFrame:
    """Pull raw snapshots joined with station metadata in ``[start, end)``.

    Streams via a server-side cursor and downcasts each chunk before
    appending. The naive ``.mappings().all()`` path peaked at ~1.5 GB for a
    2-day window because SQLAlchemy materialises every row as a Python
    dict before pandas sees it — that's an order of magnitude more than
    Render's 512 MB free-tier ceiling. Chunked reads keep peak memory
    bounded to roughly one chunk's worth of dicts at a time.
    """
    # Use a separate connection so the streaming cursor option doesn't
    # bleed into the caller's session (subsequent INSERTs would fail
    # because server-side cursors can't execute DML).
    from db.session import engine as _engine

    chunks: list[pd.DataFrame] = []
    # Streaming cursors can only execute SELECT, so the timeout bump
    # has to happen on a separate short-lived connection before we open
    # the cursor.
    with _engine.connect() as bump:
        bump.execute(text("SET statement_timeout = '600000'"))  # 10 min
        bump.commit()
    with _engine.connect().execution_options(
        stream_results=True, max_row_buffer=50_000
    ) as conn:
        for chunk in pd.read_sql_query(
            text(_RAW_SQL),
            conn,
            params={"start": start, "end": end},
            chunksize=50_000,
            parse_dates={"ts": {"utc": True}},
        ):
            chunk["bikes"] = chunk["bikes"].astype("int16")
            chunk["docks"] = chunk["docks"].astype("int16")
            chunk["capacity"] = chunk["capacity"].astype("int16")
            chunk["lat"] = chunk["lat"].astype("float32")
            chunk["lon"] = chunk["lon"].astype("float32")
            chunk["bikes_pct"] = (
                chunk["bikes"].astype("float32")
                / chunk["capacity"].where(chunk["capacity"] > 0).astype("float32")
            ).astype("float32")
            chunks.append(chunk)

    if not chunks:
        return pd.DataFrame(
            columns=[
                "station_id", "ts", "bikes", "docks",
                "capacity", "lat", "lon", "bikes_pct",
            ]
        )
    return pd.concat(chunks, ignore_index=True, copy=False)


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------


def _add_temporal(df: pd.DataFrame) -> pd.DataFrame:
    """Hour-of-day, day-of-week, weekend flag, cyclic encoding."""
    ts = df["ts"]
    df["hour"] = ts.dt.hour.astype("int8")
    df["dow"] = ts.dt.dayofweek.astype("int8")
    df["is_weekend"] = df["dow"].isin([5, 6]).astype("int8")
    # Cyclic encoding so 23:00 and 00:00 sit next to each other in feature space.
    radians = 2.0 * np.pi * df["hour"] / 24.0
    df["hour_sin"] = np.sin(radians).astype("float32")
    df["hour_cos"] = np.cos(radians).astype("float32")
    return df


def _add_lags_and_rolling(df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Lag and rolling features.

    Assumes ``df`` is already sorted by ``(station_id, ts)`` and snapshots
    sit on a regular ``config.grid_minutes`` grid. Gaps in the source data
    will produce NaN lag values, which are dropped later.
    """
    grouped = df.groupby("station_id", group_keys=False, sort=False)
    bikes_pct = df["bikes_pct"]

    # --- Lags -------------------------------------------------------------
    for lag in config.lag_minutes:
        if lag % config.grid_minutes != 0:
            raise ValueError(
                f"lag {lag} must be a multiple of grid_minutes={config.grid_minutes}"
            )
        steps = lag // config.grid_minutes
        df[f"bikes_pct_lag_{lag}m"] = (
            grouped[bikes_pct.name].shift(steps).astype("float32")
        )

    # --- Rolling mean over the trailing window ----------------------------
    roll_steps = config.rolling_minutes // config.grid_minutes
    df["bikes_pct_roll_1h"] = (
        grouped["bikes_pct"]
        .rolling(window=roll_steps, min_periods=max(2, roll_steps // 3))
        .mean()
        .reset_index(level=0, drop=True)
        .astype("float32")
    )

    # --- Short-term trend -------------------------------------------------
    df["bikes_pct_delta_15m"] = (df["bikes_pct"] - df["bikes_pct_lag_15m"]).astype(
        "float32"
    )
    return df


def _add_target(df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Target = ``bikes_pct`` at ``ts + horizon_minutes``."""
    if config.horizon_minutes % config.grid_minutes != 0:
        raise ValueError(
            f"horizon {config.horizon_minutes} must be a multiple of "
            f"grid_minutes={config.grid_minutes}"
        )
    steps = config.horizon_minutes // config.grid_minutes
    df["target"] = (
        df.groupby("station_id", group_keys=False, sort=False)["bikes_pct"]
        .shift(-steps)
        .astype("float32")
    )
    return df


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_training_frame(
    session: "Session",
    start: datetime,
    end: datetime,
    config: FeatureConfig = FeatureConfig(),
) -> pd.DataFrame:
    """Frame indexed by ``(station_id, ts)`` with features + ``target``.

    Pulls raw data with enough leading context to compute the longest lag,
    then enough trailing context to compute the target.

    Rows where the target or any lag feature is NaN are dropped — this is
    why ``[start, end)`` should reflect the *training window*, not the raw
    fetch window: we automatically pad both sides.
    """
    pad_before = timedelta(minutes=max(config.lag_minutes))
    pad_after = timedelta(minutes=config.horizon_minutes)

    raw = _load_raw(session, start - pad_before, end + pad_after)
    if raw.empty:
        return raw

    raw = _add_temporal(raw)
    raw = _add_lags_and_rolling(raw, config)
    raw = _add_target(raw, config)

    # Clip back to the requested window — the padding only existed to
    # supply context for lags + target.
    mask = (raw["ts"] >= start) & (raw["ts"] < end)
    out = raw.loc[mask].copy()

    cols = feature_columns(config) + ["ts", "target"]
    out = out[cols].dropna(subset=["target", *feature_columns(config)[10:]])
    return out.reset_index(drop=True)


def build_inference_frame(
    session: "Session",
    now: datetime,
    config: FeatureConfig = FeatureConfig(),
) -> pd.DataFrame:
    """One row per station with features as of the latest snapshot ≤ ``now``.

    No ``target`` column. Returned frame is what ``predict.py`` feeds to the
    LightGBM booster to produce ``now + horizon`` forecasts.
    """
    pad = timedelta(minutes=max(config.lag_minutes) + config.grid_minutes)
    raw = _load_raw(session, now - pad, now + timedelta(minutes=1))
    if raw.empty:
        return raw

    raw = _add_temporal(raw)
    raw = _add_lags_and_rolling(raw, config)

    # Latest snapshot per station, capped at ``now``.
    latest_idx = (
        raw.loc[raw["ts"] <= now]
        .groupby("station_id")["ts"]
        .idxmax()
    )
    out = raw.loc[latest_idx, feature_columns(config) + ["ts"]].copy()
    out = out.dropna(subset=feature_columns(config)[10:])
    return out.reset_index(drop=True)
