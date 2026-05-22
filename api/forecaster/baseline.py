"""Hour-of-week baseline forecaster.

Group by (station_id, dow, hour), take the mean of bikes_pct. Stored in the
hour_of_week_baseline table (or computed on the fly from status_hourly).
This is the benchmark every real model must beat.

Not implemented yet — see memory: project-wizard-ml-plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def train_baseline(session: "Session") -> dict:
    """Compute and store the hour-of-week mean for every station."""
    raise NotImplementedError("train_baseline: implement first, before LightGBM")


def predict_baseline(
    session: "Session", station_id: str, horizon_minutes: int
) -> float:
    """Look up the hour-of-week bucket for now + horizon."""
    raise NotImplementedError("predict_baseline: implement first, before LightGBM")
