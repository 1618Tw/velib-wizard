"""Periodic database maintenance.

`REINDEX` is the only thing here for now. We learned on 2026-05-26 that
the heavy DELETE workload on `status_snapshots` (retention drops ~400k
rows/day) accumulates bloat in the primary-key B-tree that VACUUM does
not reclaim — the index grew to 211 MB on a 169 MB table before we
caught it, pushing the DB to ~90 % of the 500 MB Supabase cap. A single
`REINDEX INDEX CONCURRENTLY` freed 126 MB. This module schedules that
operation so the win is permanent rather than something we remember to
re-do.

Why `CONCURRENTLY`: rebuilds the index alongside the live one without
holding a write lock, so collectors keep inserting throughout. Costs a
brief temporary doubling of the index size on disk; with PK ≈ 85 MB
post-fix and ~177 MB of headroom, that fits.

Why a separate engine connection: `REINDEX CONCURRENTLY` cannot run in
a transaction, so we need an AUTOCOMMIT connection rather than the
SessionLocal we use everywhere else.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import Engine, text

log = logging.getLogger("velib.maintenance")

PK_INDEX = "status_snapshots_pkey"


def reindex_status_snapshots_pkey(engine: Engine) -> dict:
    """Rebuild the `status_snapshots` PK index concurrently.

    Returns timing + before/after index size so the caller can log the
    win. Safe to call back-to-back: the second call is fast because
    there's no bloat to compact.
    """
    size_sql = text(f"SELECT pg_relation_size('{PK_INDEX}')")

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        before_bytes = int(conn.execute(size_sql).scalar_one())
        t0 = time.monotonic()
        conn.execute(text(f"REINDEX INDEX CONCURRENTLY {PK_INDEX}"))
        elapsed = time.monotonic() - t0
        after_bytes = int(conn.execute(size_sql).scalar_one())

    saved_bytes = before_bytes - after_bytes
    log.info(
        "reindex %s: %.1f MB → %.1f MB (saved %.1f MB) in %.1fs",
        PK_INDEX,
        before_bytes / 1024 / 1024,
        after_bytes / 1024 / 1024,
        saved_bytes / 1024 / 1024,
        elapsed,
    )
    return {
        "index": PK_INDEX,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "saved_bytes": saved_bytes,
        "elapsed_seconds": round(elapsed, 1),
    }
