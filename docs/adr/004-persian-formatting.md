# ADR 004 — Centralized Persian formatting (Intl, no Jalali library)

Date: 2026-10-04 · Status: accepted

## Context

All UI numbers/dates/currency must follow Persian rules (`۰-۹`, `٬` U+066C, Jalali + `٫` U+066B, Toman glyph) without drift.

## Decision

- Single layer in `packages/ui/src/lib/` (`locale/number/currency/date/jalali`) on stdlib `Intl.DateTimeFormat("fa-IR-u-ca-persian")`, plus `Price`/`PersianNumber`/`PersianDate` components.
- Toman glyph via `.toman-glyph` hook + sr-only label until the glyph font is supplied.

## Alternatives

- `jalaali-js`/`date-fns-jalali`: deferred — `Intl` covers current needs; revisit on timezone edge cases.
- Per-component formatting: rejected — guarantees drift, spec forbids.

## Consequences

- UI tests pin separators/digits; backend/DB stay numeric/Latin; glyph font drops in without component changes.
