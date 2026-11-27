# ADR 039 — Persisted AI reports and a fast analysis model

Date: 2026-11-26

## Status

Accepted. The separate `analysis_model_id` is superseded by
[ADR 040](040-admin-ai-settings-single-model.md); product analysis uses the one
configured model.

> Report persistence and the owner-only report endpoints below still hold.

## Context

The product analysis tab (ADR 037) originally kept the report only in React
state. Closing the dialog discarded it, and every reopen required another
billable model call. The owner asked for the text to survive the dialog until
the next analysis or an explicit admin delete.

Speed is equally important. The shared model (`gapgpt-deepseek-v4.1-flash`)
spends most of a minute reasoning before its first visible token; the same
prompt answered by a fast non-reasoning model starts in ~1.5 seconds and
finishes in seconds. A report that is persisted also removes the need to
regenerate it just to re-read it.

## Decision

1. Store the **last complete** report per product in a dedicated
   `product_analysis_reports` row (product id primary key, content, model id,
   generated timestamp). A newly completed analysis replaces it. Partial or
   failed streams are never saved.
2. Expose owner-only `GET` and `DELETE` on
   `/api/v1/ai/products/{product_id}/analysis/report`. The tab loads the saved
   report on open and shows a delete action with an inline confirmation.
3. Persist from the server, not the browser: the streaming generator saves the
   accumulated text through its own short write session before sending `done`.
   The client cannot choose the stored text. Saving is best-effort; a save
   failure is logged and the user still receives the finished report.
4. Add `analysis_model_id` to `ai_config`, separate from the shared `model_id`.
   It defaults to `gpt-4.1-mini` (fast, streams token-by-token, available on the
   current gateway) and is editable in AI settings. The shared model still
   drives the connection test and any future non-analysis feature.
5. Include the new table in the shop-data restore order (after `products` when
   loading, before `products` when deleting) so backups and restores stay
   FK-consistent.

## Alternatives

- **Browser localStorage**: rejected. It survives only one browser profile, has
  a small quota, and bypasses the server-side truth used by the rest of the
  panel.
- **Save partial text after an abort**: rejected. A truncated report looks like
  a finished one on the next open.
- **Switch the global model to the fast one**: rejected. It silently changes the
  connection test and any future AI feature; analysis has different latency
  needs.
- **Cache only in memory on the client**: rejected. It does not survive a
  reload or a second device, and the dialog unmounts.

## Consequences

- Schema change: migration `0029_ai_analysis_persistence` adds the column and
  table. Reports travel in backup archives and are restored with shop data.
- A report generated before the migration is not backfilled; the first open
  simply shows no saved report.
- `gpt-4.1-mini` is a gateway-specific default. If the owner points the base URL
  at a provider without it, they must set `analysis_model_id` (the error is
  visible and the shared model is untouched).
- New generations overwrite the previous report; there is no history. Owners
  who need versions can copy the text before regenerating.
- Quality of the fast model is lower than a reasoning model. The system prompt
  already constrains the structure; the model can be changed back per owner.
