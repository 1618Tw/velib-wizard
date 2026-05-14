# Vélib Wizard

A dashboard for Paris Vélib' stations with a 2-hour forecast risk score per station.

Two services:

- `web/` — Next.js dashboard (App Router, Tailwind, shadcn/ui, MapLibre).
- `api/` — FastAPI backend: GBFS / weather / OSM collectors, read API, forecaster.

Postgres for storage (local: Postgres.app; deploy: Supabase or Neon).

See the plan at `~/.claude/plans/hey-so-i-m-doing-effervescent-feather.md`.

## Quick start

Prereqs: Node 20+, Python 3.11+, Postgres 15+ running locally on `:5432`.

```bash
# 1. Backend
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit DATABASE_URL etc.
psql "$DATABASE_URL" -f db/schema.sql
uvicorn main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd web
npm install
npm run dev
```

## Milestones

- **M1** — Skeleton + GBFS collector ingesting station data.
- **M2** — Dashboard map + station detail views (live state, no forecast yet).
- **M3** — Forecast v1: hour-of-week heuristic.
- **M4** — Features (POI, weather, calendar) + LightGBM v2 model.
- **M5** — Polish: favorites, network analytics, deploy.
