# ADR 037 — Product-scoped AI analysis

Date: 2026-11-26

## Status

Accepted. Route access is superseded by
[ADR 040](040-admin-ai-settings-single-model.md): admins generate and delete
reports, and every signed-in account can read the saved report.

> The analysis design, server-built context, and privacy rules below still hold.

## Context

The owner wants an AI analyst next to every product: a report that reads the
product's sales, stock, and competitor prices and returns a decision — not a
restatement of the table. [ADR 035](035-ai-provider-foundation.md) provides the
owner-managed OpenAI-compatible connection and one shared system prompt;
[ADR 036](036-ai-streaming-sse.md) provides SSE streaming.

The data reality constrains the design:

- Sales are not stored. The product cardex is a live Parsina aggregation capped
  at 30 days, with one detail request per invoice.
- Stock is a snapshot, overwritten on every catalog sync, with no history.
- Competitor prices are the only persisted time series
  (`competitor_price_observations`); the listings endpoint exposes fresh prices,
  one daily change, and stale raw values.
- There is no previous-period, 90-day, category-sales, or own-price history.

Letting the panel send a prompt (or prompt plus data) to `/ai/stream` would make
the model's context client-controlled: prompt injection, unbounded token cost,
and no guarantee that counterparty names or invoice ids stay inside Charsooq.
The product data itself is business-sensitive even though it contains no
customer PII.

## Decision

1. Add a fourth tab, «تحلیل هوش مصنوعی», to the product detail dialog, directly
   after «کارتکس کالا». It is visible and usable only for `owner`; the report is
   generated on an explicit button, streamed into the tab, and kept while the
   dialog stays open for the same product.
2. Add `POST /api/v1/ai/products/{product_id}/analysis` (SSE, owner-only). The
   request carries no body: the client names the product and nothing else. The
   route rejects missing products with `404`, unconfigured AI with `503`, and
   otherwise emits the existing `delta` / `done` / `error` frames.
3. Build the model context in `ProductAnalysisService` and compute every metric
   there: 7/30-day sales, average daily sales, coverage days, stockout risk,
   reorder quantity/date/capital, margin, and fresh competitor average/min/max.
   The model interprets and prioritizes; it must not do arithmetic.
4. Keep the payload privacy-safe: aggregate sales only — no buyer/seller names,
   invoice ids, invoice lines, or competitor URLs. Money reaches the model as
   integer Toman; dates are pre-formatted Jalali display strings because the
   payload is model-facing, not a public API response.
5. Keep the MVP to data that exists today. The 90-day window, previous-period
   comparison, category-average sales, and price/sales elasticity are reported
   as unavailable rather than estimated. The payload is an internal contract, so
   output sections and fields can change without a migration.
6. Reuse the shared owner-managed system prompt from ADR 035; the feature sends
   only one JSON user message. No new table or Alembic revision is introduced.

## Alternatives

- **Reuse `/ai/stream` with client-supplied context**: rejected. It trusts the
  browser for data and prompt text, enables injection and cost abuse, and
  duplicates the context builder in the UI.
- **Persist daily sales first**: deferred. It is the right enabler for 90-day,
  category, and elasticity analysis, but it is a larger change (new table,
  scheduler job, backfill) and not needed for the first report.
- **Owner+admin access**: deferred. `/ai/*` is owner-only today; opening the
  analysis to admins is a separate access decision, not a side effect of this
  feature.
- **A separate analysis prompt field**: deferred. The shared prompt is the single
  AI instruction set until a second feature needs different instructions.

## Consequences

- Each report is a billable provider request and a live cardex fetch; the UI
  disables regeneration while a report is streaming and the endpoint is
  owner-only.
- A slow or unconfigured Parsina degrades to a partial report (inventory and
  market only) with an explicit data-quality note, not an error page.
- In development the cardex may be fixture/demo data; the payload marks the
  environment so the model states the limitation.
- Changing output sections is a change in the context builder and/or the system
  prompt, not a schema migration.
- If admins should see the tab later, the route guard and the `canUseAI` gate
  must change together, with a new decision for the paid-call exposure.
