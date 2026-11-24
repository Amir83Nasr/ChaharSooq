# 030 — Per-product pricing modes

Date: 2026-11-24

## Status

Accepted. Supersedes the category-based pricing-formula split described in the
suggested-price settings and in `compares_with_competitor`.

Refined by [031 — Category-scoped competitor links and unified no-price mode](031-category-competitor-links.md):
the third selector is now a persisted `pricing_mode` value (the separate
`no_competitor_price` boolean is removed), and competitor link slots depend on
the catalog section alone rather than on the mode.

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
   The **formula selector** is the product's mode, but the weight `w` remains
   configured per catalog section (four rows in `suggested_price_formulas`,
   keyed by `top_group`). One weight per category is shared by both formulas:
   it is the competitor share in the blend and the daily-change scale in the
   delta formula.
4. The product detail dialog exposes a three-way mode selector (قیمت رقیب /
   محصول مشابه / فاقد قیمت رقیب) and two tabs with the corresponding link
   settings — one for exact competitor links, one for similar-product links.
5. Existing rows are migrated by their section: carpets and furniture become
   `similar_product`, everything else `exact_competitor`. Category still
   decides _which specific store_ is offered for similar-product tracking
   (Sofa for furniture, DigiFresh for carpets), but no longer decides the
   formula.

## Consequences

- The pricing settings page keeps four category weights; the two formulas are
  presented as the two modes a product can select, both consuming the same
  per-category weight.
- CSV exports and the products table pick the formula from
  `product.pricing_mode`; category helpers remain only for display/branding
  and for choosing the tracking store.
- New API surface: `PATCH /api/v1/products/{id}/pricing-mode`; `ProductOut`
  gains `pricing_mode`. The settings formulas contract is unchanged:
  `top_group` + `weight`.
- Backup/restore is unaffected: the `suggested_price_formulas` table keeps its
  name and primary key.
