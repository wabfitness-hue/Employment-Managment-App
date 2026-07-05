# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A local, Docker-based **Employee Management System (EMS)** for managing staff and
contractors, issuing printed ID cards, and controlling door access via NFC. It runs
on a single machine (Windows host + Docker Desktop). Not multi-tenant, not cloud.

- **Backend**: FastAPI (Python 3.12), SQLAlchemy 2, PostgreSQL 16, Redis, Alembic.
- **Frontend**: React 18 + TypeScript + Vite + Tailwind, served by Nginx.
- **Auth**: JWT (python-jose) + bcrypt (passlib) + TOTP MFA (pyotp).
- **Bridge agent**: runs on the host (outside Docker) for USB NFC reader + card printer.

## Architecture

```
nginx (:80)  ──►  backend (FastAPI :8000, 2 uvicorn workers)  ──►  db (Postgres)
   │                     │                                          redis
  React SPA         scheduler (daily expiry alerts, 1 instance)
                    backup (daily pg_dump + photos → ./backups)
```

Only Nginx is exposed on the host (port 80). The backend is internal-only.
`docker-compose.yml` is the source of truth for services.

### Services (docker-compose.yml)
- `db`, `redis` — data stores (named volumes `db_data`, `redis_data`).
- `backend` — API + Alembic migrations on startup (`--workers 2`).
- `scheduler` — single-instance container running `python -m app.jobs.scheduler`;
  runs the contract-expiry sweep daily at 07:00. Separate from the web process
  **because 2 workers would each fire the job and send duplicate emails**.
- `backup` — dumps DB + photos to the host-mounted `./backups/` every 24h, 14-day
  retention. Restore steps in `backups/RESTORE.md`.
- `nginx` — serves the built SPA + reverse-proxies `/api`.

## Build & deploy workflow

**Important: Docker builds on this machine are flaky under memory pressure** (WSL
has OOM-crashed mid-build, corrupting images and leaving the backend crash-looping
on `No config file 'alembic.ini'`). To avoid this, build the frontend on the host
and package the static output — do NOT rely on the multi-stage nginx Docker build:

```bash
cd frontend && npm run build          # host build — catches TS errors fast
cd /c/Users/Simmy/employee-management-app
docker build -t employee-management-app-nginx -f - frontend/dist <<'EOF'
FROM nginx:1.27-alpine
COPY . /usr/share/nginx/html
EXPOSE 80
EOF
docker compose build backend          # backend image
docker compose up -d --no-build backend nginx scheduler backup
```

If Docker/WSL wedges (`cannot allocate memory`, `rpc error ... EOF`):
```bash
wsl --shutdown        # then wait for Docker Desktop to come back
# for a hard reset also: Stop-Process "Docker Desktop"; relaunch it
```

Always `npm run build` on the host first to catch TypeScript errors before touching
Docker — it's much faster than a container round-trip.

## Migrations

Alembic, in `backend/app/migrations/versions/` (`0001`…`0007`). They run
automatically on backend container startup. When adding a column: create the next
`000N_*.py` revision **and** update the model in `backend/app/models/`. Use a plain
`String` column with a `server_default` for extensible enums (e.g. `card_status`)
rather than a Postgres enum type — simpler to extend.

## Conventions & gotchas

- **UUIDs**: Pydantic v2 with `from_attributes=True` does NOT auto-stringify UUID
  fields typed as `str`. Add `@field_validator("id", mode="before")` returning
  `str(v)` on any response schema exposing a UUID (see `schemas/people.py`).
- **File uploads**: FastAPI can't mix a JSON `body: Model` with `File(...)` in one
  endpoint — use `Form(...)` for the other fields (see `imports.py`, `photos.py`).
- **Authenticated images**: `<img src>` can't send the auth header. Use the
  `AuthImg` component (axios blob fetch → object URL). `getPhotoUrl` returns a path
  relative to the axios baseURL `/api/v1`.
- **Employee IDs**: letter prefix + 7 random digits (e.g. `A0000001`), generated in
  `models/id_prefix.py`; uniqueness retried in `services/people.py`.
- **TOTP**: `verify_mfa_token` uses `valid_window=1` (~90s drift tolerance).
- **Config refuses to boot** on default `SECRET_KEY`/`JWT_SECRET_KEY` or `*` in
  `CORS_ORIGINS` (see `core/config.py`). Real values live in `.env`.

## Domain model

- **Person** (`people`): employee or contractor. `status` = employment
  (active/inactive/suspended/pending). `card_status` = physical card state
  (active/forgotten/temporary/lost/stolen/faulty/on_leave/returned/not_issued) —
  **separate from employment**, so a lost card never deactivates the person.
  `nfc_uid` = permanent card; `temp_nfc_uid` = temporary card while the permanent
  one is forgotten (permanent is blocked at readers until returned).
- **Contract**: employees 5yr, contractors 6mo; renewals preserve continuity.
- **Company**: one main company + contractor companies. Card design (colours, fonts,
  band/company-name colours) is stored as JSON on the main company row
  (`card_design`); see `api/v1/companies.py` `load_card_design`.
- **Access**: card taps hit `GET /people/nfc/{uid}`, which returns an access
  decision (`evaluate_card_access` in `services/people.py`). Denied if the holder
  is inactive/suspended, the card is lost/stolen/faulty/on-leave/returned, the
  contract is expired, or the forgotten permanent card is tapped while a temp is out.

## ID card generation

- PDF: `services/cards/generator.py` (ReportLab, CR80 85.6×54mm). Layout constants
  in `dimensions.py`. Honours per-type design (bg/text/accent/band/company colours,
  font). Header/footer bands auto-darken the card colour unless a band colour is set.
- On-screen preview: `components/ui/CardVisual.tsx` mirrors the PDF layout. The
  in-app **Card designer** (`components/CardDesigner.tsx`, opened from the ID Cards
  page) edits and saves the design; changes flow to both preview and PDF.
- Cards intentionally omit contract expiry and access info so they don't need
  reprinting when those change.

## Frontend layout

- Pages in `frontend/src/pages/`, API clients in `frontend/src/api/`, shared types
  in `frontend/src/types/index.ts`, Zustand stores in `frontend/src/store/`.
- Auth state: `store/auth.ts`. Bridge (NFC/printer) websocket state: `store/bridge.ts`.

## Running instance facts

- App URL: http://localhost/ — admin login `wabfitness@gmail.com`.
- DB: Postgres `ems_db` / user `ems_user` (password in `.env`). Query with
  `docker compose exec -T db psql -U ems_user -d ems_db`.
- To exercise an authenticated endpoint from the CLI, log in via
  `POST /api/v1/auth/login` inside the backend container to get a bearer token.

## Docs

- `INSTALL.md` — setup. `SECURITY.md` — security posture. `backups/RESTORE.md` —
  disaster recovery.
