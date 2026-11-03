/* Typed fetch client for the Charsooq FastAPI contract (OpenAPI-derived shapes).
   Browser always calls same-origin /api/* (Next rewrites to FastAPI);
   proxy keeps the session cookie first-party. No cross-site fetch. */

import { toPersianDigits } from "@workspace/ui/lib/number"

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

export interface ApiError {
  error: {
    code: string
    message: string
    details?: Record<string, string[]>
  }
}

export class ApiRequestError extends Error {
  status: number
  code?: string
  details?: Record<string, string[]>

  constructor(
    status: number,
    message: string,
    code?: string,
    details?: Record<string, string[]>
  ) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...init,
    })
  } catch {
    throw new ApiRequestError(
      0,
      "اتصال به سرور برقرار نشد. اتصال اینترنت را بررسی کنید."
    )
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiError | null
    throw toApiError(res.status, body)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export interface SettingsOut {
  low_stock_threshold: number
  default_page_size: number
  sync_interval_minutes: number
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

// ── Persian error mapping (never surface raw fetch/HTML/English errors) ──

export const GENERIC_ERROR_MESSAGE = "خطایی رخ داد. لطفاً دوباره تلاش کنید."

const STATUS_FALLBACK: Record<number, string> = {
  400: "درخواست نامعتبر است.",
  401: "نام کاربری یا گذرواژه نادرست است.",
  403: "دسترسی ندارید.",
  404: "یافت نشد.",
  409: "این مقدار قبلاً ثبت شده است.",
  422: "خطای اعتبارسنجی",
  429: "تلاش‌های مکرر؛ لطفاً بعداً تلاش کنید.",
}

function toApiError(status: number, body: ApiError | null): ApiRequestError {
  const raw = body?.error?.message?.trim()
  const message =
    raw && /[؀-ۿ]/.test(raw)
      ? raw
      : (STATUS_FALLBACK[status] ?? GENERIC_ERROR_MESSAGE)
  return new ApiRequestError(
    status,
    toPersianDigits(message),
    body?.error?.code,
    body?.error?.details
  )
}

export const api = {
  login(username: string, password: string) {
    return request<{ ok: boolean }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    })
  },
  settings() {
    return request<SettingsOut>("/api/v1/settings")
  },
  updateSettings(patch: SettingsUpdate) {
    return request<SettingsOut>("/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    })
  },
  me() {
    return request<{ username: string }>("/api/v1/auth/me")
  },
  logout() {
    return request<undefined>("/api/v1/auth/logout", { method: "POST" })
  },
  products(params: ProductFilters = {}) {
    const search = new URLSearchParams()
    if (params.q) search.set("q", params.q)
    if (params.category_id)
      search.set("category_id", String(params.category_id))
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
    if (params.page_size) search.set("page_size", String(params.page_size))
    const suffix = search.size ? `?${search}` : ""
    return request<ProductPage>(`/api/v1/products${suffix}`)
  },
  competitorListings(productId: number) {
    return request<CompetitorListing[]>(
      `/api/v1/products/${productId}/competitors`
    )
  },
  createCompetitorListing(
    productId: number,
    store: CompetitorStore,
    url: string
  ) {
    return request<CompetitorListing>(
      `/api/v1/products/${productId}/competitors`,
      { method: "POST", body: JSON.stringify({ store, url }) }
    )
  },
  updateCompetitorListing(
    id: number,
    patch: Partial<
      Pick<
        CompetitorListing,
        | "store"
        | "url"
        | "is_active"
        | "manual_price"
        | "manual_currency"
        | "manual_in_stock"
      >
    >
  ) {
    return request<CompetitorListing>(`/api/v1/competitors/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    })
  },
  deleteCompetitorListing(id: number) {
    return request<undefined>(`/api/v1/competitors/${id}`, { method: "DELETE" })
  },
  checkCompetitorListing(id: number) {
    return request<CompetitorListing>(`/api/v1/competitors/${id}/check`, {
      method: "POST",
    })
  },
  categories() {
    return request<CategoryOut[]>("/api/v1/categories")
  },
  createCategory(name: string) {
    return request<CategoryOut>("/api/v1/categories", {
      method: "POST",
      body: JSON.stringify({ name }),
    })
  },
  deleteCategory(id: number) {
    return request<undefined>(`/api/v1/categories/${id}`, { method: "DELETE" })
  },
  productsSummary(threshold: number) {
    return request<InventorySummary>(
      `/api/v1/products/summary?threshold=${threshold}`
    )
  },
  productGroups() {
    return request<string[]>("/api/v1/products/groups")
  },
  parsinaStatus() {
    return request<SyncStatus>("/api/v1/integrations/parsina/status")
  },
  parsinaSync() {
    return request<SyncRun>("/api/v1/integrations/parsina/sync", {
      method: "POST",
    })
  },
  /** Cancellable status read — used by the sync poller's unmount cleanup. */
  parsinaStatusSignal(signal: AbortSignal) {
    return request<SyncStatus>("/api/v1/integrations/parsina/status", {
      signal,
    })
  },
}
