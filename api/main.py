import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from collectors.gbfs import collect_station_information, collect_station_status
from config import settings
from db.session import get_session
from scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
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
