-- Vélib Wizard schema.
-- Apply with: psql "$DATABASE_URL" -f api/db/schema.sql

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS stations (
    station_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    capacity        INTEGER NOT NULL,
    poi_counts      JSONB,
    cluster_id      INTEGER,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS status_snapshots (
    station_id      TEXT NOT NULL REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,
    bikes           INTEGER NOT NULL,
    docks           INTEGER NOT NULL,
    is_renting      BOOLEAN NOT NULL,
    is_returning    BOOLEAN NOT NULL,
    PRIMARY KEY (station_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_status_ts ON status_snapshots(ts DESC);

-- Hourly downsample of status_snapshots. Populated by the retention job once
-- the raw window (5 days) has rolled past an hour bucket. Trades intra-hour
-- resolution for unbounded history at the same byte cost as ~5 raw rows.
CREATE TABLE IF NOT EXISTS status_hourly (
    station_id      TEXT NOT NULL REFERENCES stations(station_id),
    hour_ts         TIMESTAMPTZ NOT NULL,
    bikes_avg       REAL NOT NULL,
    docks_avg       REAL NOT NULL,
    bikes_min       INTEGER NOT NULL,
    bikes_max       INTEGER NOT NULL,
    docks_min       INTEGER NOT NULL,
    docks_max       INTEGER NOT NULL,
    n               INTEGER NOT NULL,
    PRIMARY KEY (station_id, hour_ts)
);

CREATE INDEX IF NOT EXISTS idx_hourly_hour ON status_hourly(hour_ts DESC);

CREATE TABLE IF NOT EXISTS weather_hourly (
    ts              TIMESTAMPTZ PRIMARY KEY,
    temp_c          REAL,
    precip_mm       REAL,
    wind_kmh        REAL
);

CREATE TABLE IF NOT EXISTS forecasts (
    station_id          TEXT NOT NULL REFERENCES stations(station_id),
    horizon_minutes     INTEGER NOT NULL,
    risk_bike           REAL NOT NULL,
    risk_dock           REAL NOT NULL,
    model_version       TEXT NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (station_id, horizon_minutes, model_version)
);

CREATE INDEX IF NOT EXISTS idx_forecasts_computed ON forecasts(computed_at DESC);

CREATE TABLE IF NOT EXISTS model_runs (
    id              SERIAL PRIMARY KEY,
    model_version   TEXT NOT NULL,
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    feature_list    TEXT[] NOT NULL,
    metrics         JSONB NOT NULL,
    notes           TEXT
);
