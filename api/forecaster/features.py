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


def _lag_via_asof(
    df: pd.DataFrame, lag_minutes: int, tolerance_minutes: int = 15
) -> pd.Series:
    """For each row in ``df`` return ``bikes_pct`` from the row whose ``ts``
    is closest to ``current_ts - lag_minutes`` (looking backward only).

    Uses ``pd.merge_asof`` with ``direction='backward'`` so we never pick
    up a future value. Robust to gaps in the source data, unlike a naive
    ``.shift(N)`` which assumes a regular grid. ``tolerance_minutes``
    bounds the slop between the requested target time and the chosen
    row — if no row exists within that window, the lag is NaN (and the
    row gets dropped downstream, as before). 15 min is 3× the nominal
    5-min grid: tight enough to keep the lag close to the intended
    horizon, loose enough to absorb the occasional missing tick.
    """
    if df.empty:
        return pd.Series([], dtype="float32", index=df.index)

    # Build target keeping `target_ts` as a tz-aware Series — using
    # .values strips the timezone and `merge_asof` then refuses to merge.
    target = pd.DataFrame(
        {
            "station_id": df["station_id"].to_numpy(),
            "ts": df["ts"] - pd.Timedelta(minutes=lag_minutes),
            "_orig_idx": np.arange(len(df)),
        }
    ).sort_values(["ts", "station_id"], kind="stable")

    src = (
        df[["station_id", "ts", "bikes_pct"]]
        .rename(columns={"bikes_pct": "_lag_value"})
        .sort_values(["ts", "station_id"], kind="stable")
    )

    merged = pd.merge_asof(
        target,
        src,
        on="ts",
        by="station_id",
        direction="backward",
        tolerance=pd.Timedelta(minutes=tolerance_minutes),
    )
    # Restore original df order.
    merged = merged.sort_values("_orig_idx", kind="stable")
    out = merged["_lag_value"].astype("float32")
    out.index = df.index
    return out


def _add_lags_and_rolling(df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Lag and rolling features.

    Lags are computed by *timestamp* via :func:`_lag_via_asof`, not by row
    position, so the function is robust to gaps in the source data. (The
    earlier ``.shift(N)`` approach broke whenever collection coverage
    dropped below ~37 rows per station in the 185-min window.)
    Rolling and delta features still use row-position windows; that's
    fine in practice because rolling tolerates partial windows via
    ``min_periods`` and the delta is anchored to the now-robust 15-min
    lag.
    """
    df = df.sort_values(["station_id", "ts"], kind="stable").reset_index(drop=True)

    # --- Lags -------------------------------------------------------------
    for lag in config.lag_minutes:
        df[f"bikes_pct_lag_{lag}m"] = _lag_via_asof(df, lag)

    # --- Rolling mean over the trailing window ----------------------------
    grouped = df.groupby("station_id", group_keys=False, sort=False)
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
    """Target = ``bikes_pct`` at ``ts + horizon_minutes``.

    Timestamp-based via :func:`pd.merge_asof` with ``direction='forward'``
    so a gap in the data doesn't produce a target that's silently 30+
    minutes off the intended horizon. A tolerance of one grid step caps
    the slop: if the nearest future row is more than ``grid + 5`` minutes
    past the target time, the label is NaN and the row is dropped.
    """
    target = pd.DataFrame(
        {
            "station_id": df["station_id"].to_numpy(),
            "ts": df["ts"] + pd.Timedelta(minutes=config.horizon_minutes),
            "_orig_idx": np.arange(len(df)),
        }
    ).sort_values(["ts", "station_id"], kind="stable")
    src = (
        df[["station_id", "ts", "bikes_pct"]]
        .rename(columns={"bikes_pct": "_target_value"})
        .sort_values(["ts", "station_id"], kind="stable")
    )
    merged = pd.merge_asof(
        target,
        src,
        on="ts",
        by="station_id",
        direction="forward",
        tolerance=pd.Timedelta(minutes=config.grid_minutes + 5),
    )
    merged = merged.sort_values("_orig_idx", kind="stable")
    df["target"] = merged["_target_value"].astype("float32").values
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
    # Pad both sides by an extra `tolerance` so the timestamp-based
    # merge_asof lookups in _add_lags_and_rolling / _add_target can find
    # a match even at the trailing edge of the window.
    lag_tolerance = timedelta(minutes=15)
    target_tolerance = timedelta(minutes=config.grid_minutes + 5)
    pad_before = timedelta(minutes=max(config.lag_minutes)) + lag_tolerance
    pad_after = timedelta(minutes=config.horizon_minutes) + target_tolerance

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
    # Pad by `lag_tolerance` past the longest lag so the timestamp-based
    # asof lookup in _add_lags_and_rolling has room to find a match at
    # the trailing edge.
    pad = timedelta(minutes=max(config.lag_minutes) + 15)
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
