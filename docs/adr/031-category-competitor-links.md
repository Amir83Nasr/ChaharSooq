# 031 — Category-scoped competitor links and unified no-price mode

Date: 2026-11-24

## Status

Accepted. Refines [030 — Per-product pricing modes](030-per-product-pricing-modes.md).

## Context

ADR 030 introduced three owner selections in the product detail dialog — «قیمت
رقیب»، «محصول مشابه»، and «فاقد قیمت رقیب» — but implemented the third as a
separate boolean (`products.no_competitor_price`) alongside the two-value
`pricing_mode`. It also offered different link slots per mode, including a
manual «other» store escape hatch.

That split caused two problems:

- The three-way selector is a single decision, yet it was persisted in two
  independent fields that could disagree.
- Link slots are a property of the catalog section, not the formula. Offering
  different slots per mode suggested the links themselves changed with the
  formula, while only the suggested-price computation changes.

## Decision

1. `pricing_mode` becomes the single three-value persisted selector:
   `exact_competitor`, `similar_product`, `no_competitor_price`. The
   `products.no_competitor_price` column and its
   `PATCH /products/{id}/no-competitor-price` endpoint are removed; the
   `missing` filter/export now selects `pricing_mode = no_competitor_price`.
2. Competitor link slots depend only on the product's top group and are
   **identical for both active modes**:
   - «کالای دیجیتال» and «لوازم خانگی»: DigiKala, TechnoLife, Torob
   - «فرش»: DigiFresh, Torob
   - «مبلمان»: Sofa, Torob
     The manual «other» store is no longer offered in the detail dialog.
3. `no_competitor_price` mode disables link entry, suppresses all
   competitor-derived table/export cells with `—`, and skips suggested-price
   calculation.
4. Manual price entry stays restricted to `exact_competitor`, because it
   replaces a fetched direct-rival price (the delta formula needs a daily
   change, which a manual value cannot provide).

## Consequences

- One persisted field drives the three-way dialog selector; no stale flag/tab
  combinations are possible.
- The two tabs in the dialog remain a presentation convenience: they show the
  same link slots and only explain which formula consumes the prices.
- Demo seeding, CSV exports, dashboard gaps, and the products filter use the
  same category→stores map and the new mode value.
- Backward compatibility for stale databases is handled by a forward migration
  that translates the old boolean into the new mode value before dropping the
  column.
