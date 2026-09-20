# Lumina Reporting MVP

Lumina is an institutional reporting MVP with a React frontend and Flask API.

## Project layout

- `lumina-reporting/frontend` — React application deployed to GitHub Pages.
- `lumina-reporting/backend` — Flask API intended for a Python application host.
- `.github/workflows` — continuous integration and frontend deployment.

GitHub Pages hosts only the static frontend. Configure `REACT_APP_API_BASE_URL` at
frontend build time when the Flask API is deployed to a separate HTTPS host. Without
that value, the frontend runs in a clearly labelled demo mode.

## Run the frontend

```bash
cd lumina-reporting/frontend
npm ci
npm start
```

## Run the API

```bash
cd lumina-reporting/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
flask --app app run
```

The development default uses SQLite. Production must set `SECRET_KEY`,
`JWT_SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS`.

Create an initial user with:

```bash
flask --app app create-user --email admin@example.com --role admin
```

A `client`-role user represents a client-portal login and requires an
existing `Client` row:

```bash
flask --app app create-user --email client@example.com --role client --client-id 1
```

## Database migrations

Schema changes are managed with Alembic (`lumina-reporting/backend/migrations`).

```bash
cd lumina-reporting/backend
alembic upgrade head
```

Against a database that predates Alembic (i.e. already has `users`/`fund_data`
created via `create_all()`), stamp it at the baseline revision once before
upgrading:

```bash
alembic stamp 8a3c6a4d1e8f
alembic upgrade head
```

`DATABASE_URL` is read the same way the app reads it; set it before running
Alembic commands against a non-default database.

## Data sources, templates, and report export

Reports can now be built from a `ReportTemplate` (a name, description, and an
ordered list of components — holdings table, performance summary, or a
commentary text block) instead of freeform JSON. Templates and data sources
are managed entirely through guided forms in the UI (`/data-sources`,
`/templates`) — no JSON or SQL editing required. A Snowflake data source
asks for a table name and a "map your columns" list rather than a query; an
API data source asks for a base URL and paths.

`POST /api/reports` with a `template_id` resolves the template against the
`Holding`/`PerformanceSnapshot` rows landed for that report's client and
renders a PDF at creation time. `GET /api/reports/<id>/export?format=pdf|
pptx|xlsx|raw` re-resolves and renders on demand in any of the four formats,
so it reflects data synced after the report was first created; a legacy
report without a template only supports `format=pdf`.

Connecting a real Snowflake account or API isn't exercised by the test
suite or by CI — both connectors are covered by mocked unit tests
(`tests/test_connectors.py`) since no live warehouse or vendor API is part
of this repo. `POST /api/data-sources/<id>/sync` also runs synchronously
inside the request; a slow warehouse query can hit an HTTP timeout in
production since there's no background task queue yet.

## Deploy to Render (backend + frontend, one click through)

`render.yaml` at the repo root is a Render Blueprint defining two
resources: the Flask API as a web service (`lumina-api`) and the React app
as a static site (`lumina-frontend`). It runs against any branch, not just
`main`.

The database is deliberately *not* provisioned by the blueprint: a Render
free account allows only one active free-tier Postgres total, so adding a
second one here fails outright if you already have one elsewhere. Instead,
`lumina-api`'s `DATABASE_URL` is left blank for you to point at any
Postgres database you already have, or a free one from
[Neon](https://neon.tech) — Neon's free tier isn't capped per-account the
way Render's is.

1. **Database**: sign up at [neon.tech](https://neon.tech) (free), create a
   project, and copy its connection string (Dashboard → Connection Details
   → looks like `postgresql://user:password@ep-xxxx.aws.neon.tech/dbname`).
2. In the Render dashboard: **New > Blueprint**, connect this repository,
   and pick the branch you want deployed (e.g.
   `claude/repository-code-review-a7hzot`). Render reads `render.yaml` and
   proposes both resources.
3. Before clicking **Apply**, Render asks for the `sync: false` values —
   fill in what you can now:
   - `lumina-api` → `DATABASE_URL` = the Neon connection string from step 1.
   - `lumina-api` → `CORS_ORIGINS` and `lumina-frontend` → `REACT_APP_API_BASE_URL`
     can't be known yet (they reference each other's URL, and neither
     service exists until after this deploy) — leave them blank for now,
     click **Apply**, and come back to them next.
4. Once both services have deployed once and you can see their assigned
   URLs, fill in the two values from step 3 in each service's Environment
   tab:
   - `lumina-api` → `CORS_ORIGINS` = the `lumina-frontend` URL (e.g.
     `https://lumina-frontend.onrender.com`).
   - `lumina-frontend` → `REACT_APP_API_BASE_URL` = the `lumina-api` URL
     (e.g. `https://lumina-api.onrender.com`).
   Redeploy both services after setting these (Manual Deploy → Deploy
   latest commit) — `CORS_ORIGINS` takes effect on `lumina-api`'s restart,
   and `REACT_APP_API_BASE_URL` is baked in at `lumina-frontend`'s build
   time, so both need a fresh deploy, not just a restart.
5. The API's build step runs `alembic upgrade head` against the Neon
   database, then `flask --app app seed-demo` — both happen automatically
   on every deploy (the free compute plan has no Shell access to run
   commands by hand, and `seed-demo` no-ops if it's already seeded, so
   running it on every build is safe). It seeds a reverse-engineered Pzena
   Global Small Cap Focused Value factsheet — real fund data, holdings,
   performance, a disclosure, a 12-component template, and a report
   already carried through the full workflow to `distributed` — plus four
   logins to click around with (all `@lumina.test`): `admin`/`admin-pass`,
   `editor`/`editor-pass`, `compliance`/`compliance-pass`,
   `client`/`client-pass`.
6. Open the `lumina-frontend` URL and log in with any of the above.

`lumina-api` is on Render's free tier and spins down after 15 minutes
idle — the first request after that takes ~30-50s to wake it up. Neon's
free tier has its own idle/storage limits; see their pricing page if the
database stops responding after a long gap.

## Verification

```bash
cd lumina-reporting/frontend && npm run build
cd ../backend && pytest
```
