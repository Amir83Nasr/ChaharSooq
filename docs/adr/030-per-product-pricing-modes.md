# 030 — Per-product pricing modes

Date: 2026-11-24

## Status

Accepted. Supersedes the category-based pricing-formula split described in the
suggested-price settings and in `compares_with_competitor`.

## Context

The suggested price used to be chosen by a product's catalog section
(top group):

- «لوازم خانگی» and «کالای دیجیتال» blended the Parsina base price with a
  direct competitor price: `P = w × Pc + (1 − w) × Pb`.
- «مبلمان» and «فرش» scaled the linked product's daily price change:
  `P = Pb × (1 + w × Δ)`.

That split was too narrow. The real distinction is not the category but the
kind of competitor link available for the product: some products have an exact
competitor product page with a trustworthy price; others only have a similar
product whose daily price change is meaningful. A carpet or a digital product
can belong to either group depending on the links the owner can provide.

A separate owner marker, `no_competitor_price`, records that no comparable
competitor price exists. It is not a pricing formula; it disables competitor
links and blanks competitor-derived cells.

## Decision

1. Every product carries a persisted `pricing_mode`:
   - `exact_competitor` — the product has an exact competitor link; the
     suggested price uses the weighted blend with the competitor price.
   - `similar_product` — the product tracks a similar product's daily change;
     the suggested price uses the delta formula.
2. `no_competitor_price` stays an independent boolean. When set, competitor
   link entry is disabled, all competitor-derived table columns render `—`,
   and no suggested price is computed.
3. The two formulas and the per-product price bounds
   (`allowed_decrease_percent` / `allowed_increase_percent`) are unchanged.
   Only the key that selects the formula and its weight changes: weights are
   stored per mode instead of per top group (two rows in
   `suggested_price_formulas`).
4. The product detail dialog exposes a three-way mode selector (قیمت رقیب /
   محصول مشابه / فاقد قیمت رقیب) and two tabs with the corresponding link
   settings — one for exact competitor links, one for similar-product links.
5. Existing rows are migrated by their section: carpets and furniture become
   `similar_product`, everything else `exact_competitor`. Category still
   decides _which specific store_ is offered for similar-product tracking
   (Sofa for furniture, DigiFresh for carpets), but no longer decides the
   formula.

## Consequences

- The pricing settings page now configures two mode weights instead of four
  category weights; the old four weights are collapsed deterministically
  during migration.
- CSV exports and the products table pick the formula from
  `product.pricing_mode`; category helpers remain only for display/branding
  and for choosing the tracking store.
- New API surface: `PATCH /api/v1/products/{id}/pricing-mode`; `ProductOut`
  gains `pricing_mode`; settings formulas use `mode` instead of `top_group`.
- Old clients sending `top_group` weights are rejected by the settings API
  with 422: `mode` is now required on every formula item. The migration
  converts existing stored rows, so saved settings remain valid.
- Backup/restore keeps the same `suggested_price_formulas` table name; only
  its primary-key column is renamed.
