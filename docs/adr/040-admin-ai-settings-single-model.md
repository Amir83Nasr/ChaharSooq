# ADR 040 — Admin-managed AI settings with a single model and shared analysis

Date: 2026-11-27

## Status

Accepted. Supersedes the owner-only access of
[ADR 035](035-ai-provider-foundation.md) for the connection settings and the
separate analysis model of
[ADR 039](039-ai-report-persistence-and-fast-model.md).

## Context

[ADR 035](035-ai-provider-foundation.md) made the AI provider configuration
owner-only, and [ADR 039](039-ai-report-persistence-and-fast-model.md) added a
second `analysis_model_id` so product reports could use a fast model. Both
decisions were made before the shop relied on an `admin` account for everyday
operation.

Two problems appeared:

- Routine configuration (rotating a key, switching a provider or model) needed
  the owner, even though `admin` already manages every other setting. The
  settings page itself was also hidden from admins.
- Two model fields were confusing: the analysis model silently defaulted to a
  gateway-specific `gpt-4.1-mini`, so a custom provider could fail only in the
  report flow while the connection test passed.

The connection-test section had also grown into a textarea plus a streamed
reply, which is more surface than a one-off health check needs.

## Decision

1. `GET`/`PUT /api/v1/ai/settings` and `POST /api/v1/ai/test` use
   `require_admin`: `owner` and `admin` can read, save, and test the shared
   configuration. Viewers still receive `403 forbidden`.
2. Remove the separate analysis model. `analysis_model_id` leaves the API
   schema, the service, and `ai_config` (migration `0030_ai_single_model`).
   Product analysis uses the same `model_id` as every other AI feature.
3. Share product analysis with management while keeping viewers read-only:
   `POST /api/v1/ai/products/{id}/analysis` and the report `DELETE` use
   `require_admin`; the report `GET` uses `require_user`. Admins get the full
   tab (generate, read, delete); viewers can open the tab and read the saved
   report but see no generate or delete action. `/api/v1/ai/stream` stays
   owner-only.
4. The AI settings page becomes available to both management roles. The large
   test panel is replaced by one «آزمایش اتصال» button next to the save action
   that calls the buffered `POST /ai/test` with a fixed prompt and shows a
   success or provider-error toast.
5. Settings remain a single shared row: both management roles edit the same
   provider, and the API key stays write-only (only `api_key_set` is returned).

## Alternatives

- **Let viewers generate reports**: rejected. Generation is a billable,
  data-consuming action, so it stays with the management roles; viewers only
  read the saved result.
- **Per-role or per-user AI configuration**: rejected. One shop, one provider
  configuration; more rows add complexity without a use case.
- **Keep the streaming test panel**: rejected. The reply text is irrelevant for
  a health check, and the buffered endpoint already returns the model and
  latency.

## Consequences

- Admins can change the provider, key, and model, and can generate and delete
  product reports. This is intended: the configuration and analysis are
  operational, not owner-private data, and the key never leaves the backend.
- Viewers can read the analysis tab but cannot spend model tokens or remove a
  report; the route guards enforce the same split as the UI.
- Migration `0030_ai_single_model` drops the stored analysis model. Reports
  generated afterwards use the shared model, so their latency and quality
  follow that model; an owner who needs a faster report model must change
  `model_id`, which affects every AI feature.
- `ai-test-panel.tsx` is removed; `/ai/stream` and its client helper stay in
  the contract but the settings page no longer consumes them.
- Tests and the committed OpenAPI snapshot reflect the single model and the
  management-role guard.
