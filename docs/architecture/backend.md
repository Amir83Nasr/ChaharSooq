# Backend — چهارسوق

FastAPI app factory in `backend/api/app/main.py` (`create_app()`), mounted at `/api/v1`.

- Layers: `app/api/routes/` (thin handlers) → `app/services/` (auth, products) → `app/repositories/` (SQLAlchemy queries) → `app/core/database.py` (engine/session).
- Boundary schemas in `app/schemas/` (Pydantic). Predictable error envelope: `{ error: { code, message, details? } }`; validation errors → `validation_error` (Persian message).
- Security: Argon2id password hashing, opaque session tokens (SHA-256 hash stored), `HttpOnly` cookie (`Secure` in production, `SameSite=Lax`), security headers, strict CORS, 10/min IP rate limit on login.
- Logging: stdlib structured-ish (`level name message`), never logs passwords, tokens, or secrets.
- OpenAPI: `backend/api/scripts/export_openapi.py` emits `backend/openapi.json`; frontend `apps/web/lib/api.ts` mirrors the contract types.
