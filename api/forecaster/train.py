"""Train the LightGBM forecaster on the training frame and persist weights.

Steps:
  1. Pick a chronological split: train ≤ T-3d, val ∈ (T-3d, T-1d], test = T-1d
     (NEVER random split — it leaks future into past).
  2. Fit LGBMRegressor with early stopping on val.
  3. Evaluate on test; log MAE and compare against baseline MAE.
  4. Save the booster to api/data/models/forecast_<horizon>m.lgb.
  5. Insert a row into model_runs with metrics + feature list.

Not implemented yet — see memory: project-wizard-ml-plan.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"


def train(session: "Session", horizon_minutes: int = 120) -> dict:
    """Train + persist. Returns metrics dict written to model_runs."""
    raise NotImplementedError("train: implement after 2026-05-26 + baseline.py done")
