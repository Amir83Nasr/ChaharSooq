/* Shared OpenAPI-derived boundary types for the Charsooq API.
   No fetch logic here — see api.ts (client) and api-params.ts (query builder). */

export interface CategoryOut {
  id: number
  name: string
  created_at: string
}

export type ProductSort =
  "category" | "alphabetical" | "newest" | "cheapest" | "most_expensive"

/**
 * Which competitor source drives this product's suggested price.
 * `no_competitor_price` is the third selection of the three-way dialog: no
 * links are offered and all competitor-derived cells render as dashes.
 */
export type PricingMode =
  "exact_competitor" | "similar_product" | "no_competitor_price"

export interface ProductOut {
  id: number
  external_id: number | null
  name: string
  /** True when an active competitor link has a fresh price (any store). */
  has_competitor_price: boolean
  /** Three-way per-product selector; independent of the catalog top group. */
  pricing_mode: PricingMode
  sku: string
  price: number
  stock: number
  main_group_name: string | null
  top_group: TopGroup | null
  sub_group_name: string | null
  unit_name: string | null
  is_active: boolean
  category: CategoryOut | null
  synced_at: string | null
  competitor_prices: CompetitorPrice[]
  allowed_decrease_percent: number | null
  allowed_increase_percent: number | null
  created_at: string
}

export interface ProductPage {
  items: ProductOut[]
  total: number
  page: number
  page_size: number
}

export type CompetitorStore =
  "digikala" | "technolife" | "sofa" | "digifresh" | "torob" | "other"
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
  price_change_percent: number | null
  previous_price: number | null
  previous_currency: CompetitorCurrency | null
  previous_observed_at: string | null
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
  price_change_percent: number | null
  previous_price: number | null
  previous_currency: CompetitorCurrency | null
  previous_observed_at: string | null
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
  /** Active products compared directly with a competitor — coverage denominator. */
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

export interface ParsinaConnectionOut {
  base_url: string
  username: string
  org_id: number | null
  fiscal_year: number | null
  password_set: boolean
  configured: boolean
  source: string
}

export interface ParsinaConnectionUpdate {
  base_url?: string | null
  username?: string | null
  password?: string | null
  org_id?: number | null
  fiscal_year?: number | null
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

export type UserRole = "owner" | "admin" | "viewer"
/** Roles the panel may assign; the owner comes from the environment. */
export type AssignableRole = Exclude<UserRole, "owner">

export interface MeOut {
  id: number
  username: string
  role: UserRole
}

export interface UserOut {
  id: number
  username: string
  role: UserRole
  created_at: string
}

export interface UserCreate {
  username: string
  password: string
  role: AssignableRole
}

export type ProductTableColumn =
  | "row"
  | "name"
  | "sku"
  | "category"
  | "brand"
  | "unit"
  | "price"
  | "competitor_price"
  | "price_diff"
  | "suggested_price"
  | "suggested_price_change"
  | "stock"

export interface SettingsOut {
  low_stock_threshold: number
  default_page_size: number
  sync_interval_minutes: number
  competitor_sync_interval_minutes: number
  suggested_price_formulas: SuggestedPriceFormula[]
  product_table_columns: ProductTableColumn[]
}

export interface BackupSettings {
  enabled: boolean
  interval_minutes: number
  retention_days: number
  verification_method: string
  tools_available: boolean
  storage_ready: boolean
}

export interface BackupSettingsUpdate {
  enabled?: boolean
  interval_minutes?: number
}

export type BackupStatus = "queued" | "running" | "completed" | "failed"
export type BackupVerification = "pending" | "verified" | "failed"
export type BackupKind = "scheduled" | "operator" | "uploaded" | "pre_restore"
export type RestoreStatus = "queued" | "running" | "completed" | "failed"

export interface BackupRecord {
  id: number
  created_at: string
  finished_at: string | null
  status: BackupStatus
  kind: BackupKind
  size_bytes: number | null
  sha256: string | null
  verification: BackupVerification
  verification_method: string | null
  source_revision: string | null
  storage_ref: string | null
  retention_expires_at: string | null
  pruned_at: string | null
  error_code: string | null
  downloadable: boolean
  restore_status: RestoreStatus | null
  restore_started_at: string | null
  restore_finished_at: string | null
  restore_error_code: string | null
  restored_at: string | null
}

export type TopGroup = "کالای دیجیتال" | "لوازم خانگی" | "فرش" | "مبلمان"

export interface SuggestedPriceFormula {
  top_group: TopGroup
  /**
   * Share applied to the source: competitor price for لوازم خانگی/کالای
   * دیجیتال, daily price change for مبلمان/فرش. Always 0–1.
   */
  weight: number
}

export interface SettingsUpdate {
  low_stock_threshold?: number
  default_page_size?: number
  sync_interval_minutes?: number
  competitor_sync_interval_minutes?: number
  suggested_price_formulas?: SuggestedPriceFormula[]
  product_table_columns?: ProductTableColumn[]
}

export interface ProductFilters {
  q?: string
  category_id?: number
  top_group?: TopGroup | readonly TopGroup[]
  main_group?: string
  min_price?: number
  max_price?: number
  competitor_store?: CompetitorStore
  pricing_mode?: PricingMode
  min_competitor_price?: number
  max_competitor_price?: number
  min_stock?: number
  max_stock?: number
  in_stock?: boolean
  sort?: ProductSort
  page?: number
  page_size?: number
}

/** `null` disables that side of the suggested-price clamp. */
export interface ProductPriceBoundsUpdate {
  allowed_decrease_percent: number | null
  allowed_increase_percent: number | null
}

export interface ProductPricingModeUpdate {
  pricing_mode: PricingMode
}
