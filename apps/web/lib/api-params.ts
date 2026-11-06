/* Shared query-param builder for the products list endpoint.
   Browser-only helper — keeps `undefined`/`""` out of the URL so the API
   sees only the filters the user actually set. */

import type { ProductFilters } from "./api-types"

export function buildProductParams(params: ProductFilters): string {
  const search = new URLSearchParams()
  if (params.q) search.set("q", params.q)
  if (params.category_id) search.set("category_id", String(params.category_id))
  if (params.top_group) search.set("top_group", params.top_group)
  if (params.main_group) search.set("main_group", params.main_group)
  if (params.min_price !== undefined)
    search.set("min_price", String(params.min_price))
  if (params.max_price !== undefined)
    search.set("max_price", String(params.max_price))
  if (params.competitor_store)
    search.set("competitor_store", params.competitor_store)
  if (params.min_competitor_price !== undefined)
    search.set("min_competitor_price", String(params.min_competitor_price))
  if (params.max_competitor_price !== undefined)
    search.set("max_competitor_price", String(params.max_competitor_price))
  if (params.min_stock !== undefined)
    search.set("min_stock", String(params.min_stock))
  if (params.max_stock !== undefined)
    search.set("max_stock", String(params.max_stock))
  if (params.in_stock !== undefined)
    search.set("in_stock", String(params.in_stock))
  if (params.sort) search.set("sort", params.sort)
  if (params.page) search.set("page", String(params.page))
  if (params.page_size !== undefined)
    search.set("page_size", String(params.page_size))
  const suffix = search.size ? `?${search}` : ""
  return suffix
}
