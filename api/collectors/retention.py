"""Retention + downsample job.

Keeps the last `RAW_KEEP_DAYS` of `status_snapshots` at 5-min cadence.
Older rows get rolled up into `status_hourly` (one row per station per hour)
and then deleted from the raw table.

Idempotent: re-runs on the same window are no-ops because the source rows
were deleted in the previous run.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

RAW_KEEP_DAYS = 5

log = logging.getLogger("velib.retention")


def downsample_and_prune(session: Session, raw_keep_days: int = RAW_KEEP_DAYS) -> dict:
    cutoff_sql = f"date_trunc('hour', now() - interval '{raw_keep_days} days')"

    # 1) Aggregate complete hours older than the cutoff into status_hourly.
    #    DO NOTHING means a re-run can't double-write; partial-hour merges
    #    can't happen because we cut on hour boundaries.
    rolled = session.execute(
        text(
            f"""
            INSERT INTO status_hourly
              (station_id, hour_ts,
               bikes_avg, docks_avg,
               bikes_min, bikes_max,
               docks_min, docks_max,
               n)
            SELECT
              station_id,
              date_trunc('hour', ts) AS hour_ts,
              avg(bikes)::real,
              avg(docks)::real,
              min(bikes), max(bikes),
              min(docks), max(docks),
              count(*)
            FROM status_snapshots
            WHERE ts < {cutoff_sql}
            GROUP BY station_id, date_trunc('hour', ts)
            ON CONFLICT (station_id, hour_ts) DO NOTHING
            """
        )
    ).rowcount

    # 2) Drop the raw rows we just rolled up.
    deleted = session.execute(
        text(f"DELETE FROM status_snapshots WHERE ts < {cutoff_sql}")
    ).rowcount

    session.commit()

    log.info("retention: %s hourly rows inserted, %s raw rows deleted", rolled, deleted)
    return {"hourly_inserted": rolled or 0, "raw_deleted": deleted or 0}
