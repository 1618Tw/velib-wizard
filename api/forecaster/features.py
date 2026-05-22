"""Build the training matrix for the forecaster.

Combines recent raw status_snapshots (last 5 days, 5-min resolution) with
older status_hourly aggregates, joins stations metadata + weather, and emits
one row per (station, ts) with lag features and the target at t+horizon.

Not implemented yet — see memory: project-wizard-ml-plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class FeatureConfig:
    horizon_minutes: int = 120
    lag_minutes: tuple[int, ...] = (15, 30, 60, 180)
    include_weather: bool = True


def build_training_frame(
    session: "Session",
    start: datetime,
    end: datetime,
    config: FeatureConfig = FeatureConfig(),
) -> "pd.DataFrame":
    """Return a frame indexed by (station_id, ts) with all features + target."""
    raise NotImplementedError("build_training_frame: implement after 2026-05-26")


def build_inference_frame(
    session: "Session",
    now: datetime,
    config: FeatureConfig = FeatureConfig(),
) -> "pd.DataFrame":
    """Return a frame with one row per station for predicting at `now`."""
    raise NotImplementedError("build_inference_frame: implement after 2026-05-26")
