# ADR 020 — Keyword-based digital section classification

Date: 2026-11-18 · Status: accepted

## Context

Parsina's `/Commodity` response supplies a free-form `mainGroupName` and
`mainGroup` id, but the API contract has no group metadata endpoint and no
"digital" flag. The section (بخش) is therefore our own classification of a
source field. The old rule matched four hard-coded prefixes and was copied into
the backend helper, the SQL filter, and the frontend, so a new group such as
«لپتاپ گیمینگ» silently fell into «لوازم خانگی». Parsina also renumbers group
ids between exports, so an id can never outrank a name.

## Decision

- Keep one canonical keyword tuple, `DIGITAL_TOKENS`, in
  `app/core/top_groups.py`. A normalized group name (Persian/Arabic letters,
  case, and extra spaces) belongs to «کالای دیجیتال» when it contains any
  keyword anywhere, not only at a fixed prefix.
- Derive the SQL `ILIKE` patterns from that same tuple
  (`DIGITAL_NAME_PATTERNS`). The filter, sort order, dashboard, and exports
  follow a keyword edit automatically.
- The backend derives the section once and exposes it as `ProductOut.top_group`;
  the frontend reads that field instead of recomputing from the raw group name.
- No new database column, mapping table, review UI, or external classifier.

## Alternatives

- Admin-managed group-to-section table with a review queue: deferred — it
  needs a migration and UI; revisit only if keyword false positives show up.
- An LLM-based classifier: rejected — no labeled data, a new dependency, and
  catalog names would leave our environment.
- More hard-coded prefixes: rejected — keeps the same drift and the duplicated
  copies across layers.

## Consequences

- Extending the rule is one edit in `DIGITAL_TOKENS`; there is no frontend
  mirror to update and no data migration.
- A digital keyword inside an appliance group name could cause a false
  positive. The dashboard's catalog breakdown already lists groups, so watch
  it after a new Parsina export and add an explicit exception if needed.
- Rows without a group name keep the existing id fallback and appear with a
  null `top_group` in the API.
