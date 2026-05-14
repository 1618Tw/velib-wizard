# Deployment — Vélib Wizard backend

The backend runs on Render's free web-service tier and writes to Postgres on Supabase's free tier. A free cron service (cron-job.org) drives the 5-min snapshot collector by hitting `/api/cron/collect-status`. The frontend stays local for now.

## One-time setup

### 1. Supabase

1. Sign in at https://supabase.com and create a project in an EU region (Frankfurt is closest to Paris). Set a strong DB password.
2. Settings → Database → Connection pooling → copy the **Transaction mode** URL (port `6543`). It looks like:
   ```
   postgres://postgres.<project>:<pw>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
   ```
3. SQLAlchemy/psycopg expect the `postgresql+psycopg://` scheme. Convert:
   ```
   postgresql+psycopg://postgres.<project>:<pw>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```
4. Apply the schema once from your machine:
   ```
   psql "$DATABASE_URL" -f api/db/schema.sql
   ```
   Verify: `psql "$DATABASE_URL" -c "\dt"` shows `stations`, `status_snapshots`, `weather_hourly`, `forecasts`, `model_runs`.

### 2. Render

1. Push the repo to GitHub (a private repo is fine).
2. https://render.com → "New +" → "Blueprint" → connect the repo → Render picks up `api/render.yaml`.
3. Render prompts for the two `sync: false` secrets:
   - `DATABASE_URL` = the Supabase URL from step 1.3 above.
   - `CRON_SECRET` = a fresh random string. Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
4. Deploy. After ~3 min, hit `https://velib-wizard-api.onrender.com/health` — expect `{"ok": true, "stations": 0, "snapshots": 0, "last_snapshot_ts": null}`.

### 3. Seed the database

Run these two commands locally (replace the URL with your Render service URL):

```
SECRET=<the CRON_SECRET you set on Render>
curl -X POST -H "X-Cron-Secret: $SECRET" https://velib-wizard-api.onrender.com/api/cron/collect-info
curl -X POST -H "X-Cron-Secret: $SECRET" https://velib-wizard-api.onrender.com/api/cron/collect-status
```

`/health` should now show `stations: ~1500`, `snapshots: ~1500`, and a recent `last_snapshot_ts`.

### 4. cron-job.org

1. https://console.cron-job.org → create job.
2. URL: `https://velib-wizard-api.onrender.com/api/cron/collect-status`
3. Method: `POST`
4. Headers: `X-Cron-Secret: <CRON_SECRET>`
5. Schedule: every 5 minutes.
6. Save and enable. Watch the execution history for an hour — every run should be a 200 with `{"inserted": ~1500}`.

### 5. Point local frontend at prod

In `web/.env.local`:

```
NEXT_PUBLIC_API_BASE=https://velib-wizard-api.onrender.com
```

Restart `npm run dev`. The map should still load (note: first request after idle takes ~30s while Render wakes — that's normal on the free tier).

## Operations

**Rotate the cron secret**:
1. Generate a new value.
2. Update `CRON_SECRET` in Render's dashboard. The service redeploys automatically.
3. Update the header value in the cron-job.org job.

**Re-seed station info** (occasionally, when Vélib adds/removes stations — they bump this monthly-ish):
```
curl -X POST -H "X-Cron-Secret: $SECRET" https://velib-wizard-api.onrender.com/api/cron/collect-info
```

**Check Render service status**: Render dashboard → the `velib-wizard-api` service shows uptime and logs.

**If Render shows the service as Suspended**: Render auto-suspends free services that have been idle for ~75 days without any deploys or settings changes. Trigger a manual deploy or push a commit to wake it.

**Database storage budget**: 5-min snapshots × 1,500 stations × 288/day × 30 days ≈ 13M rows ≈ 600 MB. The retention SQL job (added in M3+) downsamples raw rows older than 30 days into hourly aggregates to stay inside the 500 MB Supabase free tier ceiling. If we're close to the ceiling before then, switch the cron-job.org cadence from 5 to 10 minutes to halve growth.
