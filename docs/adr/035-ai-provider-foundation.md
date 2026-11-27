# ADR 035 — Owner-managed AI provider foundation

Date: 2026-11-26

## Status

Accepted. The owner-only access to the connection settings is superseded by
[ADR 040](040-admin-ai-settings-single-model.md); admins can manage the same
configuration.

> The provider boundary, write-only key, and single shared configuration below
> still hold.

## Context

Upcoming features need one AI model: a product-title assistant, pricing help,
and other catalog tasks. The provider is reached through an
OpenAI-compatible gateway (GapGPT today) whose base URL, API key, and model id
may change without a code release. The owner must be able to edit them, and
only the owner — the same sensitivity as the Parsina credentials.

The gateway supports both `POST /v1/chat/completions` and the newer
`POST /v1/responses`. The app needs a stable request path that keeps working if
the base URL later points at another OpenAI-compatible provider, and needs a
single place where the shared system prompt is prepended.

## Decision

1. Use `POST {base_url}/chat/completions`. It is the canonical
   OpenAI-compatible endpoint, supported by the current gateway and by the
   broadest set of alternative gateways. The Responses API is newer but is not
   uniformly implemented; adopting it now would couple every AI feature to one
   provider shape.
2. Store the configuration in a dedicated singleton `ai_config` table:
   `base_url`, `api_key`, `model_id`, `system_prompt`. The system prompt can be
   long, so the generic key/value `settings` table is not reused; the API key is
   not mixed with display preferences.
3. Defaults live in the service, not in the database row: base URL
   `https://api.gapgpt.ir/v1` and model id `gapgpt-deepseek-v4.1-flash`. An empty
   stored field falls back to its default, so the owner only has to enter the
   API key on first use. Clearing the system prompt clears that field.
4. Only `owner` may read or change the configuration
   (`GET/PUT /api/v1/ai/settings`) or run the connection test
   (`POST /api/v1/ai/test`). The API key is write-only: it is accepted by PUT
   and never returned; reads expose `api_key_set` and `configured` only. An
   empty or omitted key keeps the stored one, matching the Parsina password
   rule.
5. All features call `AIService.complete()` instead of building HTTP requests.
   The service owns the system prompt, credentials, timeout, and the mapping of
   provider failures to Persian messages. Feature services pass only their
   conversation messages.
6. The settings page lives at `/settings/ai`, is linked from the sidebar's
   «هوش مصنوعی» group and the settings sub-navigation, and is visible only to
   the owner. It includes a live «آزمایش اتصال» panel so the owner can verify
   the endpoint, key, and model without waiting for a feature.
7. `ai_config` is part of the shop-data restore set. Like the Parsina
   connection row it therefore travels in backup archives, which must continue
   to be protected as sensitive.

## Alternatives

- **Responses API**: rejected for now. It worked against the current gateway
  but is less portable and would require a separate adapter for providers that
  only expose chat completions.
- **Environment-only configuration**: rejected. The owner explicitly asked to
  edit the base URL, key, model, and prompt from the panel; env-only would need
  a restart and a deployment change for each rotation.
- **Reuse the generic `settings` table**: rejected. Its `String(256)` value
  column cannot hold a meaningful system prompt, and it is documented as
  display state, never secrets.
- **Per-feature model or prompt selection**: deferred. One shared system prompt
  and model keeps the first features consistent; a feature that needs its own
  instructions can pass additional messages without a schema change.

## Consequences

- Rotating the key or switching model/provider is an owner-only settings edit;
  no deploy is needed.
- The key is stored in the database in plaintext, following the existing Parsina
  credential precedent, and is protected by the same access controls (owner-only
  endpoints, no key in responses or logs). It is not encrypted at rest.
- The connection test makes a real, billable provider request when the owner
  presses the button; it is never scheduled.
- Migration `0028_ai_config` is the new Alembic head.
- Future AI features must route through `AIService.complete()` so prompt and
  credential handling does not diverge.
