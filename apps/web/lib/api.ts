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
  created_at: string
}

export interface ProductPage {
  items: ProductOut[]
  total: number
  page: number
  page_size: number
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
}

export interface SettingsUpdate {
  low_stock_threshold?: number
  default_page_size?: number
}

export interface ProductFilters {
  q?: string
  category_id?: number
  main_group?: string
  min_price?: number
  max_price?: number
  min_stock?: number
  max_stock?: number
  in_stock?: boolean
  sort?: ProductSort
  page?: number
  page_size?: number
}

// ── Persian error mapping (never surface raw fetch/HTML/English errors) ──

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
      : (STATUS_FALLBACK[status] ?? "خطایی رخ داد. لطفاً دوباره تلاش کنید.")
  return new ApiRequestError(
    status,
    toPersianDigits(message),
    body?.error.code,
    body?.error.details
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
    if (params.main_group) search.set("main_group", params.main_group)
    if (params.min_price !== undefined)
      search.set("min_price", String(params.min_price))
    if (params.max_price !== undefined)
      search.set("max_price", String(params.max_price))
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
