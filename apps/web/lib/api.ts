/* Typed fetch client for the Charsooq FastAPI contract (OpenAPI-derived shapes).
   Browser always calls same-origin /api/* (Next rewrites to FastAPI);
   proxy keeps the session cookie first-party. No cross-site fetch. */

import { toPersianDigits } from "@workspace/ui/lib/number"

import { createTtlCache } from "./api-cache"
import {
  buildCompetitorListingsExportParams,
  buildProductExportParams,
  buildProductParams,
  type CompetitorExportFilters,
} from "./api-params"
import type {
  ApiError,
  CatalogSection,
  CategoryOut,
  CompetitorGap,
  CompetitorListing,
  CompetitorStore,
  CompetitorSyncStatus,
  DashboardOverview,
  DashboardSummary,
  DefaultCompetitorStore,
  InventorySummary,
  MeOut,
  ProductFilters,
  ProductOut,
  ProductPage,
  ProductPriceBoundsUpdate,
  SettingsOut,
  SettingsUpdate,
  SyncRun,
  SyncStatus,
  UserCreate,
  UserOut,
} from "./api-types"

export type * from "./api-types"

// ── Safety cap (mirrors backend SHOW_ALL_MAX): "show all" never asks for
// more than this; the table windows the rows but the API still serializes
// them all.
export const SHOW_ALL_MAX = 2000

// Default request timeout so a hung API never leaves a page spinning forever.
// Callers with their own AbortSignal (poller cleanup) still win on abort.
const REQUEST_TIMEOUT_MS = 15_000

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
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  const signal = init?.signal
    ? AbortSignal.any([init.signal, timeout])
    : timeout
  let res: Response
  try {
    res = await fetch(path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...init,
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiRequestError(
        0,
        "پاسخ سرور طول کشید. لطفاً دوباره تلاش کنید."
      )
    }
    if (err instanceof DOMException && err.name === "AbortError") throw err
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

// Coalesces concurrent settings reads (the settings page mounts six cards
// at once) and reuses the result across navigations. Errors are never cached;
// saves refresh the entry below. Settings change rarely and every save
// refreshes this entry, so a longer TTL keeps route mounts from issuing a
// background read on every visit.
const SETTINGS_TTL_MS = 5 * 60_000
const settingsCache = createTtlCache<SettingsOut>(SETTINGS_TTL_MS)

export const api = {
  login(username: string, password: string) {
    return request<{ ok: boolean }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    })
  },
  settings() {
    return settingsCache.get(() => request<SettingsOut>("/api/v1/settings"))
  },
  updateSettings(patch: SettingsUpdate) {
    return request<SettingsOut>("/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }).then((data) => {
      settingsCache.set(data)
      return data
    })
  },
  me() {
    return request<MeOut>("/api/v1/auth/me")
  },
  logout() {
    return request<undefined>("/api/v1/auth/logout", { method: "POST" })
  },
  users() {
    return request<UserOut[]>("/api/v1/users")
  },
  createUser(payload: UserCreate) {
    return request<UserOut>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  deleteUser(id: number) {
    return request<undefined>(`/api/v1/users/${id}`, { method: "DELETE" })
  },
  products(params: ProductFilters = {}) {
    // `page_size=0` is the canonical "show all" — the backend caps it at
    // SHOW_ALL_MAX. Never rewrite it client-side: the route rejects explicit
    // sizes above 500, so sending 2000 would 422 and empty the table.
    return request<ProductPage>(`/api/v1/products${buildProductParams(params)}`)
  },
  /** CSV download URL — pass to `downloadFile`; never to `request`. */
  productExportUrl(params: ProductFilters = {}) {
    return `/api/v1/exports/products.csv${buildProductExportParams(params)}`
  },
  /** CSV download URL for competitor links; product filters narrow the rows. */
  competitorListingsExportUrl(
    params: ProductFilters = {},
    filters: CompetitorExportFilters = {}
  ) {
    return `/api/v1/exports/competitor-listings.csv${buildCompetitorListingsExportParams(params, filters)}`
  },
  updateProductPriceBounds(id: number, payload: ProductPriceBoundsUpdate) {
    return request<ProductOut>(`/api/v1/products/${id}/price-bounds`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    })
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
  checkAllCompetitorListings(productId: number) {
    return request<CompetitorListing[]>(
      `/api/v1/products/${productId}/competitors/check`,
      { method: "POST" }
    )
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
  dashboardOverview(threshold: number) {
    return request<DashboardOverview>(
      `/api/v1/dashboard/overview?threshold=${threshold}`
    )
  },
  /** Single-call dashboard payload — overview + gaps + catalog. */
  dashboardSummary(threshold: number, gapLimit = 8) {
    return request<DashboardSummary>(
      `/api/v1/dashboard/summary?threshold=${threshold}&gap_limit=${gapLimit}`
    )
  },
  dashboardGaps(limit = 8) {
    return request<CompetitorGap[]>(
      `/api/v1/dashboard/competitor-gaps?limit=${limit}`
    )
  },
  dashboardCatalogBreakdown() {
    return request<CatalogSection[]>("/api/v1/dashboard/catalog-breakdown")
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
    return statusRequest<SyncStatus>(
      "/api/v1/integrations/parsina/status",
      signal
    )
  },
  competitorStatus() {
    return request<CompetitorSyncStatus>(
      "/api/v1/integrations/competitors/status"
    )
  },
  competitorSync() {
    return request<SyncRun>("/api/v1/integrations/competitors/sync", {
      method: "POST",
    })
  },
  /** Cancellable status read — used by the sync poller's unmount cleanup. */
  competitorStatusSignal(signal: AbortSignal) {
    return statusRequest<CompetitorSyncStatus>(
      "/api/v1/integrations/competitors/status",
      signal
    )
  },
}

/** Shared cancellable GET — both sync pollers pass their unmount signal here. */
function statusRequest<T>(path: string, signal: AbortSignal): Promise<T> {
  return request<T>(path, { signal })
}
