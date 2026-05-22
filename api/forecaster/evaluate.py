"""Evaluate the model against the baseline on a holdout window.

Outputs: MAE per horizon, per station-cluster, and a single summary number
that gets logged in model_runs.metrics. The headline comparison is
  model_mae vs baseline_mae — the model is only worth shipping if it wins.

Not implemented yet — see memory: project-wizard-ml-plan.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def evaluate(
    session: "Session",
    start: datetime,
    end: datetime,
    horizon_minutes: int = 120,
) -> dict:
    """Return {model_mae, baseline_mae, n_samples, win_pct}."""
    raise NotImplementedError("evaluate: implement after train.py + baseline.py")
