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

## Verification

```bash
cd lumina-reporting/frontend && npm run build
cd ../backend && pytest
```
