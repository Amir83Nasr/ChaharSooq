"""OpenAPI metadata and shared error responses.

Route modules declare a tag once on their router and reuse the response
constants below, so each handler documents only what is specific to it.
"""

from typing import Any

from app.schemas import ErrorEnvelope

API_DESCRIPTION = """\
Administrative API for **چهارسوق (Charsooq)** — a Persian, RTL-first catalog and pricing panel.

- **Base path**: `/api/v1`
- **Authentication**: `POST /api/v1/auth/login` sets an HttpOnly session cookie.
  Send it with every protected request (`credentials: "include"` in the browser).
- **Errors**: failures use one envelope, `{"error": {"code", "message", "details?"}}`.
  `message` and `details` are user-facing Persian text.
- **Machine values**: Toman amounts, UTC timestamps, ISO dates. The UI applies
  Persian digits, grouping, and the Jalali calendar at render time.

The committed contract is `backend/api/openapi.json`; CI fails when it is stale.
"""

TAGS_METADATA: list[dict[str, Any]] = [
    {"name": "Health", "description": "Liveness and database readiness probes."},
    {"name": "Auth", "description": "Admin login, logout, and current session."},
    {"name": "Dashboard", "description": "Aggregated catalog, stock, and competitor metrics."},
    {
        "name": "Products",
        "description": "Catalog listing, creation, groups, and inventory summary.",
    },
    {"name": "Categories", "description": "Category management with an in-use delete guard."},
    {
        "name": "Competitors",
        "description": "Competitor links, manual price overrides, and price checks.",
    },
    {
        "name": "Integrations",
        "description": "Background Parsina and competitor sync jobs plus their status.",
    },
    {
        "name": "Settings",
        "description": (
            "Admin preferences: thresholds, sync intervals, pricing weights, table columns."
        ),
    },
]


def _error(model: type[ErrorEnvelope], description: str) -> dict[str, Any]:
    return {"model": model, "description": description}


UNAUTHORIZED = _error(
    ErrorEnvelope,
    "Missing, expired, or invalid session cookie (`unauthorized`).",
)
VALIDATION_ERROR = _error(
    ErrorEnvelope,
    (
        "Request validation failed (`validation_error`); `details` maps field "
        "paths to Persian messages."
    ),
)
NOT_FOUND = _error(ErrorEnvelope, "The requested resource does not exist (`not_found`).")
CONFLICT = _error(
    ErrorEnvelope,
    (
        "The request conflicts with the current state (`conflict`, or "
        "`category_in_use` for categories)."
    ),
)
RATE_LIMITED = _error(ErrorEnvelope, "Too many attempts; retry later (`rate_limited`).")
SERVICE_UNAVAILABLE = _error(
    ErrorEnvelope,
    "The product source is not configured or temporarily unavailable.",
)
