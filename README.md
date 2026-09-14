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

## Verification

```bash
cd lumina-reporting/frontend && npm run build
cd ../backend && pytest
```
