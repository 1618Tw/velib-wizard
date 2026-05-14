from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from collectors.gbfs import collect_station_information, collect_station_status
from config import settings
from db.session import get_session

app = FastAPI(title="Vélib Wizard API")

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


@app.post("/api/cron/collect-info", dependencies=[Depends(require_cron_secret)])
def cron_collect_info(session: Session = Depends(get_session)) -> dict:
    n = collect_station_information(session)
    return {"upserted": n}


@app.post("/api/cron/collect-status", dependencies=[Depends(require_cron_secret)])
def cron_collect_status(session: Session = Depends(get_session)) -> dict:
    n = collect_station_status(session)
    return {"inserted": n}
