import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from collectors.gbfs import collect_station_information, collect_station_status
from config import settings
from db.session import get_session
from scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)

PROCESS_STARTED_AT = datetime.now(tz=timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if os.environ.get("VELIB_RUN_SCHEDULER", "1") == "1":
        scheduler = build_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Vélib Wizard API", lifespan=lifespan)

# CORS: explicit origins (from ALLOWED_ORIGINS env) plus a regex for common
# preview/tunnel hosts so we don't have to touch Render every time we add a
# Vercel preview branch or fire up a quick cloudflared tunnel.
_explicit_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
_origin_regex = r"^https?://(localhost(:\d+)?|.*\.vercel\.app|.*\.trycloudflare\.com|.*\.loca\.lt)$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_explicit_origins,
    allow_origin_regex=_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def require_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=401, detail="bad cron secret")


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    stations = session.execute(text("SELECT count(*) FROM stations")).scalar_one()
    snapshots = session.execute(text("SELECT count(*) FROM status_snapshots")).scalar_one()
    last_snap = session.execute(text("SELECT max(ts) FROM status_snapshots")).scalar_one()
    return {
        "ok": True,
        "stations": stations,
        "snapshots": snapshots,
        "last_snapshot_ts": last_snap.isoformat() if last_snap else None,
    }


def _gbfs_reachable() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.head(f"{settings.gbfs_base}/station_information.json")
            return r.status_code < 400
    except Exception:
        return False


@app.get("/api/status")
def status_overview(response: Response, session: Session = Depends(get_session)) -> dict:
    now = datetime.now(tz=timezone.utc)
    row = session.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM stations) AS stations,
              (SELECT count(*) FROM forecasts) AS forecasts,
              (SELECT count(*) FROM status_snapshots) AS snapshots_total,
              (SELECT count(*) FROM status_snapshots WHERE ts >= now() - interval '1 hour') AS snapshots_1h,
              (SELECT count(*) FROM status_snapshots WHERE ts >= now() - interval '24 hours') AS snapshots_24h,
              (SELECT max(ts) FROM status_snapshots) AS last_ts,
              (SELECT min(ts) FROM status_snapshots) AS first_ts,
              pg_database_size(current_database()) AS db_bytes
            """
        )
    ).mappings().one()

    last_ts = row["last_ts"]
    minutes_since_last = (
        (now - last_ts).total_seconds() / 60.0 if last_ts is not None else None
    )

    # Sparkline: snapshots per 15-min bucket for the last 6 hours.
    buckets = session.execute(
        text(
            """
            SELECT
              to_timestamp(floor(extract(epoch FROM ts) / 900) * 900) AS bucket,
              count(*) AS n
            FROM status_snapshots
            WHERE ts >= now() - interval '6 hours'
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        )
    ).mappings().all()

    gbfs_ok = _gbfs_reachable()

    # Health verdict — fails fast if data is stale or GBFS is down.
    healthy = (
        minutes_since_last is not None
        and minutes_since_last < 15
        and gbfs_ok
    )
    if not healthy:
        response.status_code = 503

    return {
        "ok": healthy,
        "checked_at": now.isoformat(),
        "process_started_at": PROCESS_STARTED_AT.isoformat(),
        "uptime_seconds": int((now - PROCESS_STARTED_AT).total_seconds()),
        "gbfs_reachable": gbfs_ok,
        "data": {
            "stations": row["stations"],
            "forecasts": row["forecasts"],
            "snapshots_total": row["snapshots_total"],
            "snapshots_last_hour": row["snapshots_1h"],
            "snapshots_last_24h": row["snapshots_24h"],
            "last_snapshot_ts": last_ts.isoformat() if last_ts else None,
            "first_snapshot_ts": row["first_ts"].isoformat() if row["first_ts"] else None,
            "minutes_since_last_snapshot": (
                round(minutes_since_last, 1) if minutes_since_last is not None else None
            ),
            "database_bytes": int(row["db_bytes"]),
        },
        "sparkline": [
            {"bucket": b["bucket"].isoformat(), "n": int(b["n"])} for b in buckets
        ],
    }


@app.get("/api/stations")
def list_stations(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(
        text(
            """
            SELECT s.station_id, s.name, s.lat, s.lon, s.capacity,
                   ss.bikes, ss.docks, ss.ts AS last_ts
            FROM stations s
            LEFT JOIN LATERAL (
              SELECT bikes, docks, ts
              FROM status_snapshots
              WHERE station_id = s.station_id
              ORDER BY ts DESC
              LIMIT 1
            ) ss ON true
            ORDER BY s.name
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/api/stations/{station_id}")
def get_station(station_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.execute(
        text(
            """
            SELECT s.station_id, s.name, s.lat, s.lon, s.capacity,
                   s.poi_counts, s.cluster_id,
                   ss.bikes, ss.docks, ss.ts AS last_ts
            FROM stations s
            LEFT JOIN LATERAL (
              SELECT bikes, docks, ts
              FROM status_snapshots
              WHERE station_id = s.station_id
              ORDER BY ts DESC
              LIMIT 1
            ) ss ON true
            WHERE s.station_id = :sid
            """
        ),
        {"sid": station_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="station not found")
    return dict(row)


@app.get("/api/stations/{station_id}/history")
def get_station_history(
    station_id: str,
    hours: int = 24,
    session: Session = Depends(get_session),
) -> list[dict]:
    hours = max(1, min(hours, 168))
    rows = session.execute(
        text(
            """
            SELECT ts, bikes, docks
            FROM status_snapshots
            WHERE station_id = :sid
              AND ts >= now() - make_interval(hours => :h)
            ORDER BY ts ASC
            """
        ),
        {"sid": station_id, "h": hours},
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/api/network/summary")
def network_summary(session: Session = Depends(get_session)) -> dict:
    row = session.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (station_id) station_id, bikes, docks, ts
              FROM status_snapshots
              ORDER BY station_id, ts DESC
            )
            SELECT
              count(*) AS total,
              count(*) FILTER (WHERE bikes = 0) AS empty,
              count(*) FILTER (WHERE docks = 0) AS full,
              max(ts) AS last_ts
            FROM latest
            """
        )
    ).mappings().one()
    return dict(row)


@app.post("/api/cron/collect-info", dependencies=[Depends(require_cron_secret)])
def cron_collect_info(session: Session = Depends(get_session)) -> dict:
    n = collect_station_information(session)
    return {"upserted": n}


@app.post("/api/cron/collect-status", dependencies=[Depends(require_cron_secret)])
def cron_collect_status(session: Session = Depends(get_session)) -> dict:
    n = collect_station_status(session)
    return {"inserted": n}
