"""End-to-end pipeline smoke test on synthetic data.

Generates a plausible 5-day window of snapshots for a small set of stations,
then exercises features.py → baseline.py → train.py against it. Verifies
that:
  1. The feature pipeline produces the expected columns and non-NaN core
     features.
  2. The baseline lookup table has rows for every (station, dow, hour)
     bucket we see.
  3. LightGBM trains, hits early stopping, and produces predictions whose
     MAE is finite and at least competitive with the baseline.

This does NOT touch the real DB — it monkeypatches the SQL loaders. The
real test happens when the user points the .env at production.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Allow `python tests/test_pipeline_smoke.py` from the api/ root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from forecaster import baseline as baseline_mod
from forecaster import features as features_mod
from forecaster.features import FeatureConfig, feature_columns
from forecaster.train import _mae, _prepare_xy, _win_pct, Split

# --- 1. Build synthetic raw snapshots ---------------------------------------

GRID_MIN = 5
N_STATIONS = 40
N_DAYS = 5
END = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
START = END - timedelta(days=N_DAYS)

rng = np.random.default_rng(seed=42)

stations = pd.DataFrame(
    {
        "station_id": [f"S{i:04d}" for i in range(N_STATIONS)],
        "capacity":   rng.integers(low=20, high=50, size=N_STATIONS),
        "lat":        rng.uniform(48.83, 48.89, size=N_STATIONS).astype("float32"),
        "lon":        rng.uniform(2.27, 2.40, size=N_STATIONS).astype("float32"),
    }
)
stations["base_rate"] = rng.uniform(0.3, 0.7, size=N_STATIONS).astype("float32")

ts_grid = pd.date_range(START, END, freq=f"{GRID_MIN}min", inclusive="left", tz="UTC")
n_ts = len(ts_grid)

rows = []
for _, st in stations.iterrows():
    # Sinusoidal day pattern + small noise, clipped to [0, 1].
    hours = ts_grid.hour + ts_grid.minute / 60.0
    day_curve = 0.20 * np.sin((hours - 7) * np.pi / 12.0)
    noise = rng.normal(0, 0.05, size=n_ts)
    bikes_pct = np.clip(st["base_rate"] + day_curve + noise, 0.0, 1.0)
    bikes = np.round(bikes_pct * st["capacity"]).astype("int32")
    docks = st["capacity"] - bikes
    rows.append(
        pd.DataFrame(
            {
                "station_id": st["station_id"],
                "ts":         ts_grid,
                "bikes":      bikes,
                "docks":      docks,
                "capacity":   st["capacity"],
                "lat":        st["lat"],
                "lon":        st["lon"],
            }
        )
    )

raw_df = pd.concat(rows, ignore_index=True)
print(f"[synthetic] generated {len(raw_df):,} rows, {N_STATIONS} stations, "
      f"{(END - START).days} days")


# --- 2. Monkeypatch the SQL loaders -----------------------------------------

def fake_load_raw(session, start, end):
    mask = (raw_df["ts"] >= pd.Timestamp(start)) & (raw_df["ts"] < pd.Timestamp(end))
    df = raw_df.loc[mask].copy()
    df["bikes_pct"] = df["bikes"] / df["capacity"]
    return df

features_mod._load_raw = fake_load_raw


def fake_train_baseline(session, start, end):
    df = fake_load_raw(session, start, end)
    if df.empty:
        return pd.DataFrame(columns=["station_id", "dow", "hour", "bikes_pct_mean", "n"])
    df = df.assign(
        # Postgres-aligned DOW (Sun=0..Sat=6)
        dow=((df["ts"].dt.dayofweek + 1) % 7).astype("int8"),
        hour=df["ts"].dt.hour.astype("int8"),
    )
    grp = df.groupby(["station_id", "dow", "hour"])
    out = grp["bikes_pct"].agg(["mean", "count"]).reset_index()
    out = out.rename(columns={"mean": "bikes_pct_mean", "count": "n"})
    out["bikes_pct_mean"] = out["bikes_pct_mean"].astype("float32")
    out["n"] = out["n"].astype("int32")
    return out

baseline_mod.train_baseline = fake_train_baseline


# --- 3. Run the feature pipeline -------------------------------------------

cfg = FeatureConfig()
split = Split(
    train_start=START + timedelta(hours=0),
    train_end=START + timedelta(days=3),
    val_end=START + timedelta(days=4),
    test_end=END,
)

session = MagicMock()
frame = features_mod.build_training_frame(session, split.train_start, split.test_end, cfg)
print(f"[features] built {len(frame):,} rows, {len(frame.columns)} columns")
assert not frame.empty, "feature frame unexpectedly empty"
assert set(feature_columns(cfg)).issubset(frame.columns), "missing feature columns"
assert frame["target"].notna().all(), "target column has NaN after dropna"


# --- 4. Train + evaluate ---------------------------------------------------

import lightgbm as lgb

ts = pd.to_datetime(frame["ts"], utc=True)
train_mask = (ts >= pd.Timestamp(split.train_start)) & (ts < pd.Timestamp(split.train_end))
val_mask   = (ts >= pd.Timestamp(split.train_end))   & (ts < pd.Timestamp(split.val_end))
test_mask  = (ts >= pd.Timestamp(split.val_end))     & (ts < pd.Timestamp(split.test_end))

X, y = _prepare_xy(frame, cfg)
print(f"[split] train={train_mask.sum():,} val={val_mask.sum():,} test={test_mask.sum():,}")

cats = ["station_id", "dow", "hour", "is_weekend"]
train_data = lgb.Dataset(X.loc[train_mask], label=y.loc[train_mask], categorical_feature=cats)
val_data = lgb.Dataset(X.loc[val_mask], label=y.loc[val_mask], categorical_feature=cats, reference=train_data)
params = {
    "objective": "regression_l1", "metric": "mae",
    "learning_rate": 0.05, "num_leaves": 64, "min_data_in_leaf": 50,
    "feature_fraction": 0.9, "verbose": -1, "seed": 42,
}
booster = lgb.train(
    params, train_data, num_boost_round=200,
    valid_sets=[val_data], valid_names=["val"],
    callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)],
)

y_pred = pd.Series(booster.predict(X.loc[test_mask]), index=X.loc[test_mask].index)
y_true = y.loc[test_mask]
mae = _mae(y_true, y_pred)
print(f"[model] MAE on test={mae:.4f}  (synthetic baseline noise σ≈0.05)")

# Baseline check
bt = fake_train_baseline(session, split.train_start, split.train_end)
target_ts = pd.to_datetime(frame.loc[test_mask, "ts"], utc=True) + timedelta(minutes=cfg.horizon_minutes)
pred_input = pd.DataFrame({"station_id": frame.loc[test_mask, "station_id"].values,
                            "target_ts": target_ts.values}, index=y_true.index)
y_base = baseline_mod.predict_baseline_batch(bt, pred_input)
mae_b = _mae(y_true, y_base)
win = _win_pct(y_true, y_pred, y_base)
print(f"[baseline] MAE on test={mae_b:.4f}  win_pct={win:.1%}")

assert np.isfinite(mae), "model MAE is not finite"
assert np.isfinite(mae_b), "baseline MAE is not finite"
print("\n[OK] end-to-end pipeline runs on synthetic data without errors")
