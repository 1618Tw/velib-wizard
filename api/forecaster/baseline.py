"""Hour-of-week mean baseline.

For each station and each (day-of-week, hour) bucket, take the mean of
``bikes_pct`` over the training window. At prediction time, look up the
bucket for the target timestamp.

This is the benchmark a real model has to beat. If LightGBM cannot win
against this lookup table, something is wrong with the features or split.

Storage choice: in-memory DataFrame, computed on demand. We avoid a new
``hour_of_week_baseline`` table for v1 — the lookup runs in milliseconds
over a few thousand rows, no need for persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


_BUCKET_SQL = """
SELECT
    ss.station_id,
    EXTRACT(DOW   FROM ss.ts AT TIME ZONE 'UTC')::int AS dow,
    EXTRACT(HOUR  FROM ss.ts AT TIME ZONE 'UTC')::int AS hour,
    AVG(ss.bikes::float / NULLIF(s.capacity, 0))      AS bikes_pct_mean,
    COUNT(*)                                           AS n
FROM status_snapshots ss
JOIN stations s ON s.station_id = ss.station_id
WHERE ss.ts >= :start AND ss.ts < :end
GROUP BY ss.station_id, dow, hour
"""


def train_baseline(
    session: "Session",
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Compute the (station_id, dow, hour) → mean(bikes_pct) lookup table.

    Args:
        start: inclusive lower bound of the training window.
        end:   exclusive upper bound. Must NOT overlap the holdout — the
               caller is responsible for chronological discipline.

    Returns:
        DataFrame with columns
        ``[station_id, dow, hour, bikes_pct_mean, n]``.
        Empty if no rows exist in the window.
    """
    rows = session.execute(
        text(_BUCKET_SQL), {"start": start, "end": end}
    ).mappings().all()
    if not rows:
        return pd.DataFrame(
            columns=["station_id", "dow", "hour", "bikes_pct_mean", "n"]
        )
    df = pd.DataFrame(rows)
    df["station_id"] = df["station_id"].astype(str)
    df["dow"] = df["dow"].astype("int8")
    df["hour"] = df["hour"].astype("int8")
    df["bikes_pct_mean"] = df["bikes_pct_mean"].astype("float32")
    df["n"] = df["n"].astype("int32")
    return df


def predict_baseline(
    table: pd.DataFrame,
    station_id: str,
    target_ts: datetime,
) -> float | None:
    """Single-row lookup. Returns ``None`` if the bucket is missing.

    The fallback for an empty bucket is the caller's job (eg. average over
    the whole table, or the station's overall mean). Returning ``None``
    keeps that decision explicit instead of silently substituting.
    """
    target_ts_utc = target_ts.astimezone(target_ts.tzinfo) if target_ts.tzinfo else target_ts
    dow = target_ts_utc.weekday()  # Python: Mon=0..Sun=6
    # Postgres EXTRACT(DOW) returns Sun=0..Sat=6 — align to Postgres.
    dow_pg = (dow + 1) % 7
    hour = target_ts_utc.hour

    match = table[
        (table["station_id"] == station_id)
        & (table["dow"] == dow_pg)
        & (table["hour"] == hour)
    ]
    if match.empty:
        return None
    return float(match["bikes_pct_mean"].iloc[0])


def predict_baseline_batch(
    table: pd.DataFrame,
    frame: pd.DataFrame,
    target_col: str = "target_ts",
) -> pd.Series:
    """Vectorised lookup over a DataFrame of ``(station_id, target_ts)``.

    Returns a Series aligned with ``frame.index`` containing the predicted
    ``bikes_pct``. Missing buckets are filled with the *station's* overall
    mean; if that's also missing, the *global* table mean.
    """
    if frame.empty or table.empty:
        return pd.Series(dtype="float32", index=frame.index)

    ts = pd.to_datetime(frame[target_col], utc=True)
    # Postgres-aligned DOW (Sun=0..Sat=6) for consistency with the lookup table.
    dow_pg = ((ts.dt.dayofweek + 1) % 7).astype("int8")
    hour = ts.dt.hour.astype("int8")

    lookup = pd.DataFrame(
        {
            "station_id": frame["station_id"].astype(str).values,
            "dow": dow_pg.values,
            "hour": hour.values,
        },
        index=frame.index,
    )
    merged = lookup.merge(
        table[["station_id", "dow", "hour", "bikes_pct_mean"]],
        on=["station_id", "dow", "hour"],
        how="left",
    )

    # Fallback 1: station mean
    station_mean = table.groupby("station_id")["bikes_pct_mean"].mean()
    merged["bikes_pct_mean"] = merged["bikes_pct_mean"].fillna(
        merged["station_id"].map(station_mean)
    )
    # Fallback 2: global mean
    merged["bikes_pct_mean"] = merged["bikes_pct_mean"].fillna(
        float(table["bikes_pct_mean"].mean())
    )

    result = merged["bikes_pct_mean"].astype("float32")
    result.index = frame.index
    return result
