"""GBFS collectors for the Vélib feed.

Two functions, both idempotent:

- `collect_station_information`: upserts station rows. Run daily.
- `collect_station_status`: appends a snapshot row per station. Run every 5 min.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings


def _get(path: str) -> dict:
    url = f"{settings.gbfs_base}/{path}"
    with httpx.Client(timeout=20.0) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def collect_station_information(session: Session) -> int:
    data = _get("station_information.json")
    stations = data["data"]["stations"]
    rows = [
        {
            "station_id": str(s["station_id"]),
            "name": s["name"],
            "lat": s["lat"],
            "lon": s["lon"],
            "capacity": s.get("capacity", 0),
        }
        for s in stations
    ]
    session.execute(
        text(
            """
            INSERT INTO stations (station_id, name, lat, lon, capacity, updated_at)
            VALUES (:station_id, :name, :lat, :lon, :capacity, now())
            ON CONFLICT (station_id) DO UPDATE
              SET name = EXCLUDED.name,
                  lat = EXCLUDED.lat,
                  lon = EXCLUDED.lon,
                  capacity = EXCLUDED.capacity,
                  updated_at = now()
            """
        ),
        rows,
    )
    session.commit()
    return len(rows)


def collect_station_status(session: Session) -> int:
    data = _get("station_status.json")
    last_updated = data.get("last_updated")
    ts = (
        datetime.fromtimestamp(last_updated, tz=timezone.utc)
        if last_updated
        else datetime.now(tz=timezone.utc)
    )
    rows = []
    for s in data["data"]["stations"]:
        bikes = sum(
            t.get("count", 0)
            for t in s.get("num_bikes_available_types", [])
        ) or s.get("num_bikes_available", 0)
        docks = s.get("num_docks_available", 0)
        rows.append(
            {
                "station_id": str(s["station_id"]),
                "ts": ts,
                "bikes": int(bikes),
                "docks": int(docks),
                "is_renting": bool(s.get("is_renting", True)),
                "is_returning": bool(s.get("is_returning", True)),
            }
        )

    # Filter out station_ids that aren't in `stations` yet. Vélib occasionally
    # adds a new station to the feed before our daily station_information
    # refresh has run; without this filter the FK would fail the whole batch.
    # Lost rows are at most one per station per tick until the next info
    # refresh — trivial vs the cost of dropping the entire batch.
    known_ids = {
        r[0]
        for r in session.execute(text("SELECT station_id FROM stations")).all()
    }
    filtered = [r for r in rows if r["station_id"] in known_ids]

    if filtered:
        session.execute(
            text(
                """
                INSERT INTO status_snapshots
                  (station_id, ts, bikes, docks, is_renting, is_returning)
                VALUES (:station_id, :ts, :bikes, :docks, :is_renting, :is_returning)
                ON CONFLICT (station_id, ts) DO NOTHING
                """
            ),
            filtered,
        )
    session.commit()
    return len(filtered)
