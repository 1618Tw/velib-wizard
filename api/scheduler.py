"""In-process scheduler used during local dev.

Wires the collectors to APScheduler so they run on a fixed cadence whenever
the FastAPI app is up. In prod we'd swap this for an external cron hitting
the `/api/cron/*` endpoints — keeps the server stateless.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from collectors.gbfs import collect_station_information, collect_station_status
from db.session import SessionLocal

log = logging.getLogger("velib.scheduler")


def _run_status() -> None:
    with SessionLocal() as session:
        n = collect_station_status(session)
        log.info("status snapshot: %d rows", n)


def _run_info() -> None:
    with SessionLocal() as session:
        n = collect_station_information(session)
        log.info("station info refresh: %d rows", n)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Paris")
    scheduler.add_job(_run_status, "interval", minutes=5, id="status", max_instances=1)
    scheduler.add_job(_run_info, "cron", hour=4, minute=0, id="info_daily")
    return scheduler
