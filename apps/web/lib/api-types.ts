/* Shared OpenAPI-derived boundary types for the Charsooq API.
   No fetch logic here — see api.ts (client) and api-params.ts (query builder). */

export interface CategoryOut {
  id: number
  name: string
  created_at: string
}

export type ProductSort = "newest" | "cheapest" | "most_expensive"

export interface ProductOut {
  id: number
  external_id: number | null
  name: string
  sku: string
  price: number
  stock: number
  main_group_name: string | null
  sub_group_name: string | null
  unit_name: string | null
  is_active: boolean
  category: CategoryOut | null
  synced_at: string | null
  competitor_prices: CompetitorPrice[]
  created_at: string
}

export interface ProductPage {
  items: ProductOut[]
  total: number
  page: number
  page_size: number
}

export type CompetitorStore = "digikala" | "technolife" | "other"
export type CompetitorCurrency = "IRR" | "IRT"
export type CompetitorStatus =
  | "pending"
  | "success"
  | "not_found"
  | "unavailable"
  | "blocked"
  | "failed"
  | "manual"

export interface CompetitorListing {
  id: number
  product_id: number
  store: CompetitorStore
  url: string
  is_active: boolean
  status: CompetitorStatus
  fetched_price: number | null
  fetched_currency: CompetitorCurrency | null
  fetched_in_stock: boolean | null
  manual_price: number | null
  manual_currency: CompetitorCurrency | null
  manual_in_stock: boolean | null
  effective_price: number | null
  effective_currency: CompetitorCurrency | null
  effective_in_stock: boolean | null
  price_is_fresh: boolean
  last_checked_at: string | null
  last_success_at: string | null
  manual_updated_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface CompetitorPrice {
  id: number
  store: CompetitorStore
  url: string
  status: CompetitorStatus
  price: number | null
  currency: CompetitorCurrency | null
  in_stock: boolean | null
  is_fresh: boolean
  is_manual: boolean
  last_checked_at: string | null
}

export interface InventorySummary {
  total: number
  in_stock: number
  low: number
  out: number
  stock_value: number
}

export interface DashboardGroup {
  name: string
  count: number
  stock_value: number
}

export interface DashboardOverview extends InventorySummary {
  competitor_coverage: number
  /** Active لوازم خانگی items — the coverage denominator. */
  appliance_total: number
  groups: DashboardGroup[]
}

export interface CompetitorGap {
  product_id: number
  name: string
  our_price: number
  competitor_price: number
  competitor_store: CompetitorStore
  diff_percent: number
}

export interface CatalogBrand {
  group_name: string
  brand: string
  count: number
  stock_value: number
}

export interface CatalogSection {
  top_group: string
  items: number
  group_count: number
  brand_count: number
  stock_value: number
  brands: CatalogBrand[]
}

/** Aggregated dashboard payload — one fetch instead of three. */
export interface DashboardSummary {
  overview: DashboardOverview
  gaps: CompetitorGap[]
  catalog: CatalogSection[]
}

export interface SyncStatus {
  configured: boolean
  /** Live Parsina API, dev-database simulation, or local CSV fixture. */
  source: "parsina" | "csv" | "dev"
  running: boolean
  running_since: string | null
  last_attempt_at: string | null
  last_success_at: string | null
  last_error: string | null
  last_processed: number
  last_created: number
  last_updated: number
  last_deactivated: number
  last_skipped: number
  interval_minutes: number
}

/** Accepted trigger; counters arrive through SyncStatus polling. */
export interface SyncRun {
  status: "running"
  message: string | null
}

export interface CompetitorSyncStatus {
  running: boolean
  running_since: string | null
  last_attempt_at: string | null
  last_success_at: string | null
  last_error: string | null
  last_checked: number
  last_updated: number
  last_failed: number
  last_skipped: number
}

export interface ApiError {
  error: {
    code: string
    message: string
    details?: Record<string, string[]>
  }
}

export interface SettingsOut {
  low_stock_threshold: number
  default_page_size: number
  sync_interval_minutes: number
  competitor_sync_interval_minutes: number
  default_competitor_store: DefaultCompetitorStore
  suggested_price_formulas: SuggestedPriceFormula[]
}

export type TopGroup = "فرش" | "مبلمان" | "لوازم خانگی"

export type DefaultCompetitorStore = "digikala" | "technolife"

export interface SuggestedPriceFormula {
  top_group: TopGroup
  expression: string
}

export interface SettingsUpdate {
  low_stock_threshold?: number
  default_page_size?: number
  sync_interval_minutes?: number
  competitor_sync_interval_minutes?: number
  default_competitor_store?: DefaultCompetitorStore
  suggested_price_formulas?: SuggestedPriceFormula[]
}

export interface ProductFilters {
  q?: string
  category_id?: number
  top_group?: string
  main_group?: string
  min_price?: number
  max_price?: number
  competitor_store?: CompetitorStore
  min_competitor_price?: number
  max_competitor_price?: number
  min_stock?: number
  max_stock?: number
  in_stock?: boolean
  sort?: ProductSort
  page?: number
  page_size?: number
}
