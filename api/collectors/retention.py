"""Retention job.

Keeps the last `RAW_KEEP_DAYS` of `status_snapshots` at 5-min cadence and
prunes stale rows from `forecasts` (only the latest forecast per
station+horizon is useful; older ones are never read).

Idempotent: re-runs on the same window are no-ops.

Note: the status_hourly rollup was removed — that table was only used by a
one-off weather experiment (run 2026-06-04, finding: no MAE improvement) and
is now permanently empty. Writing to it again would waste ~100 MB/month with
no benefit.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

RAW_KEEP_DAYS = 5

log = logging.getLogger("velib.retention")


def downsample_and_prune(session: Session, raw_keep_days: int = RAW_KEEP_DAYS) -> dict:
    cutoff_sql = f"date_trunc('hour', now() - interval '{raw_keep_days} days')"

    # 1) Drop raw snapshots older than the retention window.
    deleted = session.execute(
        text(f"DELETE FROM status_snapshots WHERE ts < {cutoff_sql}")
    ).rowcount

    # 2) Drop stale forecasts — keep only the latest computed_at per
    #    (station_id, horizon_minutes). The map and API always read the
    #    freshest forecast; older ones accumulate silently and cost ~80 MB/month.
    forecasts_deleted = session.execute(
        text("""
            DELETE FROM forecasts
            WHERE computed_at < (
                SELECT max(computed_at) - interval '1 hour'
                FROM forecasts
            )
        """)
    ).rowcount

    session.commit()

    log.info(
        "retention: %s raw snapshots deleted, %s stale forecasts deleted",
        deleted, forecasts_deleted,
    )
    return {
        "raw_deleted": deleted or 0,
        "forecasts_deleted": forecasts_deleted or 0,
    }
