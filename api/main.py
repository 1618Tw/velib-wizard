import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from collectors.gbfs import collect_station_information, collect_station_status
from collectors.maintenance import reindex_status_snapshots_pkey
from collectors.retention import downsample_and_prune
from config import settings
from db.session import get_session
from forecaster import predict as forecaster_predict
from forecaster import train as forecaster_train
from notifier import alerts_enabled, send_email_alert
from scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)

PROCESS_STARTED_AT = datetime.now(tz=timezone.utc)

# In-memory dedupe for health alerts. Lost on restart — that's acceptable;
# the cost of a duplicate alert after a deploy is much smaller than missing
# the real one.
_LAST_ALERT_AT: datetime | None = None
_LAST_ALERT_KIND: str | None = None
STALE_MINUTES = 15
# Hourly rollups lag the live data by `RAW_KEEP_DAYS` by design (5d). We
# allow an extra cushion before screaming so a single skipped cron run
# doesn't trigger noise.
RETENTION_LAG_BUDGET_HOURS = 12
RAW_KEEP_DAYS = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if os.environ.get("VELIB_RUN_SCHEDULER", "1") == "1":
        scheduler = build_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Vélib Wizard API", lifespan=lifespan)

# CORS: explicit origins (from ALLOWED_ORIGINS env) plus a regex for common
# preview/tunnel hosts so we don't have to touch Render every time we add a
# Vercel preview branch or fire up a quick cloudflared tunnel.
_explicit_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
_origin_regex = r"^https?://(localhost(:\d+)?|.*\.vercel\.app|.*\.trycloudflare\.com|.*\.loca\.lt)$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_explicit_origins,
    allow_origin_regex=_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def require_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=401, detail="bad cron secret")


def _retention_stale(
    now: datetime,
    oldest_snapshot: datetime | None,
    last_hourly: datetime | None,
) -> bool:
    """True when the downsample/prune job has fallen behind its budget.

    Two cases:
    1. ``status_hourly`` empty AND raw history already extends past
       RAW_KEEP_DAYS — retention should have produced rows by now.
    2. ``status_hourly`` populated but its newest hour lags the live
       data by more than RAW_KEEP_DAYS + the cushion.
    """
    grace = timedelta(days=RAW_KEEP_DAYS, hours=RETENTION_LAG_BUDGET_HOURS)
    if last_hourly is None:
        if oldest_snapshot is None:
            return False  # nothing collected at all — handled by stale check
        return (now - oldest_snapshot) > grace
    return (now - last_hourly) > grace


def _maybe_send_alert(kind: str, subject: str, body: str) -> bool:
    """Emit an alert email, but at most once per cooldown window per kind."""
    global _LAST_ALERT_AT, _LAST_ALERT_KIND
    now = datetime.now(tz=timezone.utc)
    cooldown = timedelta(minutes=settings.alert_cooldown_minutes)
    if (
        _LAST_ALERT_AT is not None
        and _LAST_ALERT_KIND == kind
        and (now - _LAST_ALERT_AT) < cooldown
    ):
        return False
    sent = send_email_alert(subject, body)
    if sent:
        _LAST_ALERT_AT = now
        _LAST_ALERT_KIND = kind
    return sent


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    stations = session.execute(text("SELECT count(*) FROM stations")).scalar_one()
    snapshots = session.execute(text("SELECT count(*) FROM status_snapshots")).scalar_one()
    last_snap = session.execute(text("SELECT max(ts) FROM status_snapshots")).scalar_one()
    last_hourly = session.execute(text("SELECT max(hour_ts) FROM status_hourly")).scalar_one()
    first_snap = session.execute(text("SELECT min(ts) FROM status_snapshots")).scalar_one()

    now = datetime.now(tz=timezone.utc)
    minutes_since_last = (
        (now - last_snap).total_seconds() / 60.0 if last_snap is not None else None
    )
    retention_stale = _retention_stale(now, first_snap, last_hourly)

    # Side effect: trigger an alert email when the system is unhealthy. The
    # keep-warm cron hits this endpoint every 4 min, so this acts as our
    # in-code monitor without needing any extra external service.
    if alerts_enabled():
        if minutes_since_last is None or minutes_since_last >= STALE_MINUTES:
            _maybe_send_alert(
                kind="stale",
                subject="Data is stale",
                body=(
                    f"No new snapshot in the last {minutes_since_last:.1f} min "
                    f"(threshold {STALE_MINUTES} min).\n"
                    f"stations={stations} snapshots={snapshots} "
                    f"last_snap={last_snap.isoformat() if last_snap else 'never'}\n\n"
                    f"Check: https://console.cron-job.org and the Render logs."
                ),
            )
        if retention_stale:
            lag = (
                (now - last_hourly).total_seconds() / 3600.0
                if last_hourly is not None
                else None
            )
            _maybe_send_alert(
                kind="retention_stale",
                subject="Retention/downsample stalled",
                body=(
                    f"status_hourly.max(hour_ts) lags the live data by "
                    f"{lag:.1f}h "
                    f"(budget {RAW_KEEP_DAYS * 24 + RETENTION_LAG_BUDGET_HOURS}h).\n"
                    f"last_hourly={last_hourly.isoformat() if last_hourly else 'never'}\n\n"
                    f"Check cron-job.org has an active recurring job for "
                    f"POST /api/cron/retention."
                ),
            )

    return {
        "ok": True,
        "stations": stations,
        "snapshots": snapshots,
        "last_snapshot_ts": last_snap.isoformat() if last_snap else None,
        "minutes_since_last_snapshot": (
            round(minutes_since_last, 1) if minutes_since_last is not None else None
        ),
        "last_hourly_ts": last_hourly.isoformat() if last_hourly else None,
        "retention_stale": retention_stale,
        "alerts_enabled": alerts_enabled(),
    }


def _gbfs_reachable() -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.head(f"{settings.gbfs_base}/station_information.json")
            return r.status_code < 400
    except Exception:
        return False


@app.get("/api/status")
def status_overview(response: Response, session: Session = Depends(get_session)) -> dict:
    now = datetime.now(tz=timezone.utc)
    row = session.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM stations) AS stations,
              (SELECT count(*) FROM forecasts) AS forecasts,
              (SELECT count(*) FROM status_snapshots) AS snapshots_total,
              (SELECT count(*) FROM status_snapshots WHERE ts >= now() - interval '1 hour') AS snapshots_1h,
              (SELECT count(*) FROM status_snapshots WHERE ts >= now() - interval '24 hours') AS snapshots_24h,
              (SELECT max(ts) FROM status_snapshots) AS last_ts,
              (SELECT min(ts) FROM status_snapshots) AS first_ts,
              (SELECT max(hour_ts) FROM status_hourly) AS last_hourly_ts,
              pg_database_size(current_database()) AS db_bytes
            """
        )
    ).mappings().one()

    last_ts = row["last_ts"]
    last_hourly_ts = row["last_hourly_ts"]
    minutes_since_last = (
        (now - last_ts).total_seconds() / 60.0 if last_ts is not None else None
    )
    retention_stale = _retention_stale(now, row["first_ts"], last_hourly_ts)
    hours_since_last_hourly = (
        round((now - last_hourly_ts).total_seconds() / 3600.0, 1)
        if last_hourly_ts is not None
        else None
    )

    # Sparkline: snapshots per 15-min bucket for the last 6 hours.
    buckets = session.execute(
        text(
            """
            SELECT
              to_timestamp(floor(extract(epoch FROM ts) / 900) * 900) AS bucket,
              count(*) AS n
            FROM status_snapshots
            WHERE ts >= now() - interval '6 hours'
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        )
    ).mappings().all()

    gbfs_ok = _gbfs_reachable()

    # Health verdict — fails fast if data is stale, GBFS is down, or the
    # downsample/prune job has fallen behind. We *include* retention here so
    # the dashboard goes red instead of silently letting the DB balloon.
    healthy = (
        minutes_since_last is not None
        and minutes_since_last < 15
        and gbfs_ok
        and not retention_stale
    )
    if not healthy:
        response.status_code = 503

    return {
        "ok": healthy,
        "checked_at": now.isoformat(),
        "process_started_at": PROCESS_STARTED_AT.isoformat(),
        "uptime_seconds": int((now - PROCESS_STARTED_AT).total_seconds()),
        "gbfs_reachable": gbfs_ok,
        "data": {
            "stations": row["stations"],
            "forecasts": row["forecasts"],
            "snapshots_total": row["snapshots_total"],
            "snapshots_last_hour": row["snapshots_1h"],
            "snapshots_last_24h": row["snapshots_24h"],
            "last_snapshot_ts": last_ts.isoformat() if last_ts else None,
            "first_snapshot_ts": row["first_ts"].isoformat() if row["first_ts"] else None,
            "minutes_since_last_snapshot": (
                round(minutes_since_last, 1) if minutes_since_last is not None else None
            ),
            "last_hourly_ts": last_hourly_ts.isoformat() if last_hourly_ts else None,
            "hours_since_last_hourly": hours_since_last_hourly,
            "retention_stale": retention_stale,
            "database_bytes": int(row["db_bytes"]),
        },
        "sparkline": [
            {"bucket": b["bucket"].isoformat(), "n": int(b["n"])} for b in buckets
        ],
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


@app.get("/api/stations/{station_id}")
def get_station(station_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.execute(
        text(
            """
            SELECT s.station_id, s.name, s.lat, s.lon, s.capacity,
                   s.poi_counts, s.cluster_id,
                   ss.bikes, ss.docks, ss.ts AS last_ts
            FROM stations s
            LEFT JOIN LATERAL (
              SELECT bikes, docks, ts
              FROM status_snapshots
              WHERE station_id = s.station_id
              ORDER BY ts DESC
              LIMIT 1
            ) ss ON true
            WHERE s.station_id = :sid
            """
        ),
        {"sid": station_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="station not found")
    return dict(row)


@app.get("/api/stations/{station_id}/history")
def get_station_history(
    station_id: str,
    hours: int = 24,
    session: Session = Depends(get_session),
) -> list[dict]:
    hours = max(1, min(hours, 168))
    rows = session.execute(
        text(
            """
            SELECT ts, bikes, docks
            FROM status_snapshots
            WHERE station_id = :sid
              AND ts >= now() - make_interval(hours => :h)
            ORDER BY ts ASC
            """
        ),
        {"sid": station_id, "h": hours},
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/api/network/summary")
def network_summary(session: Session = Depends(get_session)) -> dict:
    row = session.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (station_id) station_id, bikes, docks, ts
              FROM status_snapshots
              ORDER BY station_id, ts DESC
            )
            SELECT
              count(*) AS total,
              count(*) FILTER (WHERE bikes = 0) AS empty,
              count(*) FILTER (WHERE docks = 0) AS full,
              max(ts) AS last_ts
            FROM latest
            """
        )
    ).mappings().one()
    return dict(row)


@app.post("/api/cron/test-alert", dependencies=[Depends(require_cron_secret)])
def cron_test_alert() -> dict:
    sent = send_email_alert(
        "Test alert",
        "This is a manual test from /api/cron/test-alert. If you can read this, "
        "the alert pipeline is wired up correctly.",
    )
    return {"sent": sent, "alerts_enabled": alerts_enabled()}


@app.post("/api/cron/collect-info", dependencies=[Depends(require_cron_secret)])
def cron_collect_info(session: Session = Depends(get_session)) -> dict:
    n = collect_station_information(session)
    return {"upserted": n}


@app.post("/api/cron/collect-status", dependencies=[Depends(require_cron_secret)])
def cron_collect_status(session: Session = Depends(get_session)) -> dict:
    n = collect_station_status(session)
    return {"inserted": n}


@app.post("/api/cron/retention", dependencies=[Depends(require_cron_secret)])
def cron_retention(session: Session = Depends(get_session)) -> dict:
    return downsample_and_prune(session)


def _reindex_background() -> None:
    """Run the REINDEX on its own AUTOCOMMIT connection."""
    from db.session import engine

    try:
        result = reindex_status_snapshots_pkey(engine)
        logging.info("background reindex ok: %s", result)
    except Exception:
        logging.exception("background reindex failed")


@app.post("/api/cron/reindex", dependencies=[Depends(require_cron_secret)])
def cron_reindex(background_tasks: BackgroundTasks) -> dict:
    """Schedule a CONCURRENT REINDEX of the status_snapshots PK index.

    Heavy DELETE workload from retention bloats the B-tree without
    VACUUM ever compacting it; without periodic REINDEX the PK grows
    unbounded (we observed 211 MB on a 169 MB table). Returns 202
    immediately so cron-job.org doesn't sit on the connection for the
    ~30–90 s it takes to rebuild.
    """
    background_tasks.add_task(_reindex_background)
    return {"status": "scheduled", "index": "status_snapshots_pkey"}


# ---------------------------------------------------------------------------
# Forecaster cron + reads
# ---------------------------------------------------------------------------


DEFAULT_HORIZONS = [15, 30, 45, 60, 90, 120]


def _train_horizons_background(horizons: list[int]) -> None:
    """Train each horizon in sequence with a fresh session per booster.

    Runs after the HTTP response is flushed. Each booster gets its own
    transaction so a single horizon failing doesn't cascade. We force a
    full ``gc.collect()`` between horizons because Render's 512 MB free
    tier is a hair away from OOM with the training frame; without the
    explicit GC the previous run's pandas objects may still be reachable
    from cyclic refs when the next one starts loading.
    """
    import gc
    from db.session import SessionLocal

    for h in horizons:
        try:
            with SessionLocal() as session:
                forecaster_train.train(session, horizon_minutes=h)
            forecaster_predict.reset_booster_cache(h)
            logging.info("background train succeeded for horizon=%dm", h)
        except Exception:
            logging.exception("background train failed for horizon=%dm", h)
        finally:
            gc.collect()


@app.post("/api/cron/train-forecast", dependencies=[Depends(require_cron_secret)])
def cron_train_forecast(
    background_tasks: BackgroundTasks,
    horizon: int | None = None,
) -> dict:
    """Schedule training and return immediately.

    Training a single LightGBM model on prod data takes ~2-3 min; four
    horizons together would exceed the Render HTTP timeout. We hand the
    work off to a background task so cron-job.org sees a fast 202 and
    flags only real scheduling failures, not the long-running fit itself.

    Pass ``?horizon=120`` to train a single horizon (handy for debugging);
    omit it to train the full set ``DEFAULT_HORIZONS``.
    """
    horizons = [horizon] if horizon else list(DEFAULT_HORIZONS)
    background_tasks.add_task(_train_horizons_background, horizons)
    return {"status": "scheduled", "horizons": horizons}


def _refresh_horizons_background(horizons: list[int]) -> None:
    """Run the per-horizon refresh after the HTTP response is flushed.

    Each horizon gets its own session so a single horizon failing doesn't
    cascade. Missing boosters are logged and skipped, mirroring the old
    inline behaviour.
    """
    from db.session import SessionLocal

    for h in horizons:
        try:
            with SessionLocal() as session:
                result = forecaster_predict.refresh_forecasts(
                    session, horizon_minutes=h
                )
            logging.info("background refresh ok for horizon=%dm: %s", h, result)
        except FileNotFoundError as e:
            logging.warning("background refresh: no booster for horizon=%dm (%s)", h, e)
        except Exception:
            logging.exception("background refresh failed for horizon=%dm", h)


@app.post("/api/cron/refresh-forecasts", dependencies=[Depends(require_cron_secret)])
def cron_refresh_forecasts(
    background_tasks: BackgroundTasks,
    horizon: int | None = None,
    sync: bool = False,
) -> dict:
    """Schedule the per-horizon refresh and return immediately.

    Refreshing all horizons takes several seconds on warm boosters and
    much longer on a cold Render instance, which exceeded cron-job.org's
    30 s response timeout (observed 2026-05-26). Returning a fast 202
    keeps the cron happy and lets the work complete asynchronously,
    mirroring the train-forecast pattern.

    Pass ``?horizon=120`` to refresh a single horizon; omit it to refresh
    the full ``DEFAULT_HORIZONS`` set. Pass ``?sync=true`` for a
    synchronous run that returns the per-horizon result (including any
    exception detail) — useful when the background task is silently
    failing and you need to see what's wrong.
    """
    horizons = [horizon] if horizon else list(DEFAULT_HORIZONS)
    if sync:
        from db.session import SessionLocal

        results: dict[int, dict] = {}
        for h in horizons:
            try:
                with SessionLocal() as session:
                    results[h] = forecaster_predict.refresh_forecasts(
                        session, horizon_minutes=h
                    )
            except FileNotFoundError as e:
                results[h] = {"error": "no_booster", "detail": str(e)}
            except Exception as e:
                logging.exception("sync refresh failed for horizon=%dm", h)
                results[h] = {"error": type(e).__name__, "detail": str(e)}
        return {"mode": "sync", "horizons": horizons, "results": results}

    background_tasks.add_task(_refresh_horizons_background, horizons)
    return {"status": "scheduled", "horizons": horizons}


@app.get("/api/stations/{station_id}/forecast")
def station_forecast(
    station_id: str,
    horizon: int = 120,
    session: Session = Depends(get_session),
) -> dict:
    """Latest stored forecast for one station. 404 if never computed."""
    result = forecaster_predict.predict_one(session, station_id, horizon)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"no forecast for station {station_id} at horizon {horizon}m",
        )
    return result


@app.get("/api/model-runs")
def model_runs(
    limit: int = 30,
    session: Session = Depends(get_session),
) -> dict:
    """Recent training runs per horizon, for the drift panel.

    Returns the last ``limit`` rows of ``model_runs`` for each distinct
    ``horizon_minutes`` value, oldest-first within each horizon so the
    frontend can draw a left-to-right time series. Fields are pulled out
    of the ``metrics`` jsonb so the client doesn't need to know the
    storage shape.
    """
    rows = session.execute(
        text(
            """
            WITH ranked AS (
              SELECT
                trained_at,
                model_version,
                (metrics->>'horizon_minutes')::int   AS horizon_minutes,
                (metrics->>'mae_test')::float        AS mae_test,
                (metrics->>'mae_val')::float         AS mae_val,
                (metrics->>'baseline_mae_test')::float AS baseline_mae,
                (metrics->>'win_pct')::float         AS win_pct,
                (metrics->>'n_test')::int            AS n_test,
                ROW_NUMBER() OVER (
                  PARTITION BY (metrics->>'horizon_minutes')::int
                  ORDER BY trained_at DESC
                ) AS rn
              FROM model_runs
            )
            SELECT trained_at, model_version, horizon_minutes,
                   mae_test, mae_val, baseline_mae, win_pct, n_test
            FROM ranked
            WHERE rn <= :limit
            ORDER BY horizon_minutes, trained_at ASC
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return {
        "limit": limit,
        "n_runs": len(rows),
        "runs": [
            {
                "trained_at": r["trained_at"].isoformat(),
                "model_version": r["model_version"],
                "horizon_minutes": int(r["horizon_minutes"]),
                "mae_test": float(r["mae_test"]) if r["mae_test"] is not None else None,
                "mae_val": float(r["mae_val"]) if r["mae_val"] is not None else None,
                "baseline_mae": float(r["baseline_mae"]) if r["baseline_mae"] is not None else None,
                "win_pct": float(r["win_pct"]) if r["win_pct"] is not None else None,
                "n_test": int(r["n_test"]) if r["n_test"] is not None else None,
            }
            for r in rows
        ],
    }


@app.get("/api/forecasts/risk")
def forecasts_risk(
    horizon: int = 120,
    session: Session = Depends(get_session),
) -> dict:
    """Latest forecast for every station — feeds the map's risk coloring.

    Returns one row per station with the most recent forecast at the given
    horizon. Joined with station metadata so the frontend can render
    without a second round-trip.
    """
    rows = session.execute(
        text(
            """
            SELECT DISTINCT ON (f.station_id)
                f.station_id,
                f.risk_bike,
                f.risk_dock,
                f.predicted_pct,
                f.model_version,
                f.computed_at,
                s.name,
                s.lat,
                s.lon,
                s.capacity
            FROM forecasts f
            JOIN stations s ON s.station_id = f.station_id
            WHERE f.horizon_minutes = :h
            ORDER BY f.station_id, f.computed_at DESC
            """
        ),
        {"h": horizon},
    ).mappings().all()
    return {
        "horizon_minutes": horizon,
        "n_stations": len(rows),
        "stations": [
            {
                "station_id": r["station_id"],
                "name": r["name"],
                "lat": r["lat"],
                "lon": r["lon"],
                "capacity": r["capacity"],
                "risk_bike": float(r["risk_bike"]),
                "risk_dock": float(r["risk_dock"]),
                "predicted_pct": (
                    float(r["predicted_pct"])
                    if r["predicted_pct"] is not None
                    else None
                ),
                "model_version": r["model_version"],
                "computed_at": r["computed_at"].isoformat(),
            }
            for r in rows
        ],
    }
