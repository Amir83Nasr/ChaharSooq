# ADR 034 — Pinned products and two pricing modes

Date: 2026-11-24

## Status

Accepted. Supersedes the no-competitor-price portions of
[030 — Per-product pricing modes](030-per-product-pricing-modes.md) and
[031 — Category-scoped competitor links and unified no-price mode](031-category-competitor-links.md).

## Context

ADR 031 made «فاقد قیمت رقیب» a third persisted `pricing_mode`. That mode did
double duty: it selected no suggested-price formula, suppressed every
competitor-derived cell, and disabled link entry. Owners also used it as a way
to set a product aside, but the mode was not a bookmark — it changed how the
product was priced.

The owner asked to remove the concept from the product filters, the search UI,
and the product dialog, keeping only «قیمت رقیب» and «محصول مشابه». A separate
marker is needed for the "set aside and revisit later" workflow, and it must be
independent of the pricing formula.

## Decision

1. `pricing_mode` is a two-value selector: `exact_competitor` and
   `similar_product`. `no_competitor_price` is rejected by the API on both the
   list filter and the PATCH endpoint.
2. Existing rows with `pricing_mode = 'no_competitor_price'` become
   `exact_competitor` in a forward migration. Historical migrations are never
   rewritten.
3. Products gain a persisted `pinned: Boolean NOT NULL DEFAULT false` column
   with an index. `ProductOut.pinned` exposes the marker; `ProductFilters.pinned`
   (and the matching query parameter on `GET /products` and
   `GET /exports/products.csv`) selects pinned or unpinned rows.
4. `PATCH /products/{id}/pin` sets the marker. The product dialog offers a pin
   toggle beside the pricing-mode selector, and the products toolbar offers a
   separate پین filter for revisiting pinned products. The old «فاقد قیمت رقیب»
   choice is removed from both.
5. Pinning has no effect on suggested-price calculation, competitor links, or
   CSV column suppression. Every product keeps one of the two formulas.

## Consequences

- Competitor cells and suggested price are always computed for both modes;
  empty cells now only mean missing links, stale prices, or missing weights.
- The products filter and CSV export share the new `pinned` parameter, so an
  owner can revisit pinned rows and export exactly that view.
- ADR 030/031 remain in the record for their formula and link-slot decisions;
  only their no-price statements are retired.
- Migration `0027_pinned_and_two_modes` is the new Alembic head.
