# NEXUS Prime Current Architecture Baseline

Generated for `NEXUS_PRIME_CODEX_PLAN.md` Phase 0 on 2026-06-20.

## Snapshot Context

- Branch: `upgrade/nexus-prime-plan`
- Source of truth: current worktree, not a clean `origin/master` checkout.
- Current worktree already contains many application changes plus the first backend modularization step:
  - `backend/app/domains/`
  - `backend/app/platform/crud/resource_registry.py`
  - registry-backed generic CRUD resources
- The legacy monolith remains under `legacy/monolith-flask/` and is not part of the active runtime.

## Runtime Shape

```text
frontend/ Angular 21 SPA
backend/  Flask REST API modular monolith
docs/     delivery, deployment, architecture, and baseline documentation
scripts/  local dev, clean, quality gate, preflight, deploy, API audit
legacy/   old Flask/Jinja2 snapshot for comparison only
```

## Backend Layout

Current active backend layers:

```text
backend/app/
├── api/             # Flask blueprint modules and compatibility generic CRUD
├── domains/         # domain resource/config facades introduced by Phase 1 work
├── models/          # existing SQLAlchemy models retained for compatibility
├── platform/        # shared platform services, currently CRUD registry
├── services/        # existing application/business services
├── utils/           # security, time, storage helpers
├── __init__.py      # create_app, extensions, CORS, logging, health, commands
├── commands.py
├── exceptions.py
└── extensions.py
```

Domain modules currently present:

```text
ai
content
files
finance
identity
integration
inventory
master_data
notifications
procurement
reporting
sales
workflow
```

Each domain currently has at least:

```text
__init__.py
api.py
models.py
resources.py
schemas.py
application/__init__.py
domain/__init__.py
infrastructure/__init__.py
```

## Backend Routing Baseline

- Flask app factory: `backend/app/__init__.py:create_app`
- Main API blueprint: `backend/app/api/__init__.py`, mounted at `/api/v1`
- Generic legacy-compatible routes:
  - `GET /api/v1/<resource>`
  - `POST /api/v1/<resource>`
  - `GET /api/v1/<resource>/<int:item_id>`
  - `PUT/PATCH /api/v1/<resource>/<int:item_id>`
  - `DELETE /api/v1/<resource>/<int:item_id>`
- New-path compatibility routes:
  - `GET/POST /api/v1/<path:new_path>`
  - `GET/PUT/PATCH/DELETE /api/v1/<path:new_path>/<int:item_id>`

Resource configuration is now registered from `backend/app/domains/*/resources.py` through `ResourceRegistry`, while `app.api.routes.RESOURCE_CONFIG` and `resource_config()` remain available for compatibility.

## Data Baseline

- Local development database defaults to SQLite under `backend/instance/`.
- Production target remains PostgreSQL/Supabase according to existing deployment docs.
- No Phase 0 schema migration has been applied.
- Current models still live under `backend/app/models/` and are imported by domain `models.py` facades.

## Frontend Layout

```text
frontend/src/app/
├── app.routes.ts       # Angular route source of truth
├── core/               # API, auth, guards, navigation, domain services
├── pages/              # standalone page components
└── shell/              # application shell/topbar/module map
```

Current route snapshot is recorded in `docs/frontend-routes-current.md`.

## Baseline Risks

- The worktree is not clean; many changes predate this baseline.
- `scripts/install-dependencies.ps1 -Force` currently fails on Python 3.13 when building `psycopg2-binary==2.9.9`; targeted test dependencies can still run after installing missing Flask runtime packages.

## Phase 0 Verification

| Check | Command | Result |
| --- | --- | --- |
| Branch created | `git switch -c upgrade/nexus-prime-plan` | Passed; current branch is `upgrade/nexus-prime-plan`. |
| Backend focused pytest | `cd backend; ..\venv\Scripts\python.exe -m pytest tests\test_resource_registry.py tests\test_routes.py tests\test_api.py::test_products_crud_and_pagination tests\test_api.py::test_admin_only_resource_rejects_normal_user tests\test_api.py::test_competitive_experience_api_paths -q` | Passed: `7 passed`. |
| Frontend build | `cd frontend; npm run build` | Passed after minimal compatibility fixes in Angular imports, guard return type, shell route state, runtime config typing, and global style entries. |
| API route snapshot | `create_app('testing').url_map` | Recorded in `docs/api-current.md`. |
| API contract audit | `venv\Scripts\python.exe scripts\audit-api-contracts.py` | Passed: `233/233` frontend endpoint uses matched against `122` runtime routes and `31` resources. |
| Frontend route snapshot | `frontend/src/app/app.routes.ts` | Recorded in `docs/frontend-routes-current.md`. |

## Next Architecture Step

Continue Phase 1 by splitting `backend/app/api/routes.py` into focused route modules while keeping the `/api/v1` URL surface stable.
