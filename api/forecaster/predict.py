"""Load the trained model once, batch-infer all stations on demand.

The booster is loaded lazily on the first call and cached in-process.
refresh_forecasts() runs every 15 min via cron and writes into `forecasts`.

Not implemented yet — see memory: project-wizard-ml-plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def refresh_forecasts(session: "Session", horizon_minutes: int = 120) -> dict:
    """Batch-predict every station at now+horizon and upsert into forecasts."""
    raise NotImplementedError("refresh_forecasts: implement after train.py")


def predict_one(
    session: "Session", station_id: str, horizon_minutes: int = 120
) -> float:
    """Read the most recent stored forecast for a station."""
    raise NotImplementedError("predict_one: implement after train.py")
