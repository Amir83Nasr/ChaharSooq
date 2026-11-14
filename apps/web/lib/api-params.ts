/* Shared query-param builders for the products list and CSV export endpoints.
   Browser-only helper — keeps `undefined`/`""` out of the URL so the API
   sees only the filters the user actually set. */

import type {
  CompetitorStatus,
  CompetitorStore,
  ProductFilters,
  ProductTableColumn,
} from "./api-types"

export interface CompetitorExportFilters {
  store?: CompetitorStore
  status?: CompetitorStatus
  is_active?: boolean
}

export interface ProductExportOptions {
  /** Visible table columns, in display order (export mirrors the table). */
  columns?: readonly ProductTableColumn[]
  /** Selected competitor market for the competitor/suggested columns. */
  market?: string
}

function appendProductParams(
  search: URLSearchParams,
  params: ProductFilters
): void {
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
}

function suffix(search: URLSearchParams): string {
  return search.size ? `?${search}` : ""
}

export function buildProductParams(params: ProductFilters): string {
  const search = new URLSearchParams()
  appendProductParams(search, params)
  return suffix(search)
}

/** Export endpoints accept the same filters, never paging. */
export function buildProductExportParams(
  params: ProductFilters,
  options: ProductExportOptions = {}
): string {
  const search = new URLSearchParams()
  appendProductParams(search, {
    ...params,
    page: undefined,
    page_size: undefined,
  })
  if (options.columns && options.columns.length > 0) {
    search.set("columns", options.columns.join(","))
  }
  if (options.market) search.set("market", options.market)
  return suffix(search)
}

/** Listing export = product filters + listing-specific filters. */
export function buildCompetitorListingsExportParams(
  params: ProductFilters,
  filters: CompetitorExportFilters = {}
): string {
  const search = new URLSearchParams()
  appendProductParams(search, {
    ...params,
    page: undefined,
    page_size: undefined,
  })
  if (filters.store) search.set("store", filters.store)
  if (filters.status) search.set("status", filters.status)
  if (filters.is_active !== undefined)
    search.set("is_active", String(filters.is_active))
  return suffix(search)
}
