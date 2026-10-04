# API contract — چهارسوق

Base path `/api/v1`. FastAPI serves the live contract at `/openapi.json` (UI at `/docs`).

Committed snapshot: [backend/openapi.json](../../backend/openapi.json) — regenerate after any route/schema change:

```bash
uv run --project backend/api python backend/api/scripts/export_openapi.py
```

The frontend client (`apps/web/lib/api.ts`) mirrors these shapes; keep it in sync manually until codegen lands.

Endpoint details: [architecture/api.md](../architecture/api.md).
