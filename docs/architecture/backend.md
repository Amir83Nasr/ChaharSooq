# Backend — چهارسوق

FastAPI app factory in `backend/api/app/main.py` (`create_app()`), mounted at `/api/v1`.

- Layers: `app/api/routes/{auth,products,categories,settings,health}.py` (thin handlers) → `app/services/{auth,catalog,competitor,products,settings,sync}.py` (business rules) → `app/repositories/{auth,catalog,competitor,products,settings,sync}.py` (SQLAlchemy queries) → `app/core/database.py` (engine/session). Shared `__init__.py` files re-export the public names so handlers import from the package. No SQL outside repositories.
- Models/schemas mirror the same domains: `app/models/{auth,sessions,catalog,settings}.py`, `app/schemas/{auth,catalog,settings,common}.py`.
- Shared deps live in `app/api/dependencies.py` (`get_db`, `get_current_admin`, `require_admin`); shared guards in `app/core/{errors,rate_limit}.py`. `main.py` only wires middleware + routers. Standalone ops scripts live in `scripts/` (`common.py` holds the shared session/env helpers).
- Tests mirror domains: `tests/{test_auth,test_products,test_categories,test_settings}.py` + `tests/helpers.py` (login/seed); `tests/conftest.py` owns the in-memory DB fixture.
- Product data sources: `app/integrations/sources.py` picks live Parsina (`parsina.py`) in production, the dev database mirror (`dev_db.py`, when `DEV_DATABASE_URL` is set) as a production simulation, or the `data/parsina.csv` fixture (`parsina_csv.py`) in development; `ProductSyncService` validates/applies all three through one path. The scheduler runs in development too (CSV, same interval and lock) — only tests never start it. `make db-seed-parsina` replaces the dev product mirror; `make db-clear-products` empties it (dev only). The export has no unit titles (`/UnitCount/BaseInfo` is a separate call), so the CSV source maps `countUnit` ids to mock titles — every field the production list returns is populated in dev.
- Inventory stats: `GET /products/summary` aggregates server-side (total/in/low/out/stock_value); the frontend never pages the whole catalog for stats.
- Boundary schemas in `app/schemas/` (Pydantic). Predictable error envelope: `{ error: { code, message, details? } }`; validation errors → `validation_error` (Persian message).
- Security: Argon2id password hashing, opaque session tokens (SHA-256 hash stored), `HttpOnly` cookie (`Secure` in production, `SameSite=Lax`), security headers, strict CORS, 10/min IP rate limit on login.
- Logging: stdlib structured-ish (`level name message`), never logs passwords, tokens, or secrets.
- OpenAPI: `backend/api/scripts/export_openapi.py` emits `backend/api/openapi.json`; frontend `apps/web/lib/api.ts` mirrors the contract types.
