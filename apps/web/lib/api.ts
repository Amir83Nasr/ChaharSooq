/* Typed fetch client for the Charsooq FastAPI contract (OpenAPI-derived shapes).
   All user-facing messages are Persian — never surface raw fetch/parse errors. */

import { toPersianDigits } from "@workspace/ui/lib/number"

export interface CategoryOut {
  id: number
  name: string
  created_at: string
}

export type ProductSort = "newest" | "cheapest" | "most_expensive"

export interface ProductOut {
  id: number
  name: string
  sku: string
  price: number
  stock: number
  category: CategoryOut | null
  created_at: string
}

export interface ProductPage {
  items: ProductOut[]
  total: number
  page: number
  page_size: number
}

export interface ApiError {
  error: {
    code: string
    message: string
    details?: Record<string, string[]>
  }
}

function resolveBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL
  if (typeof window === "undefined") return configured ?? "http://localhost:8000"
  const host = window.location.hostname
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
    return configured ?? "http://localhost:8000"
  }
  // ponytail: LAN dev — same host :8000؛ production به NEXT_PUBLIC_API_URL صریح نیاز دارد.
  if (configured && !configured.includes("localhost") && !configured.includes("127.0.0.1")) {
    return configured
  }
  return `http://${host}:8000`
}

export class ApiRequestError extends Error {
  status: number
  code?: string
  details?: Record<string, string[]>

  constructor(status: number, message: string, code?: string, details?: Record<string, string[]>) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${resolveBase()}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...init,
    })
  } catch {
    throw new ApiRequestError(0, "اتصال به سرور برقرار نشد. اتصال اینترنت را بررسی کنید.")
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiError | null
    throw toApiError(res.status, body)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export interface ProductFilters {
  q?: string
  category_id?: number
  min_price?: number
  max_price?: number
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
  const raw = body?.error.message?.trim()
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
  me() {
    return request<{ username: string }>("/api/v1/auth/me")
  },
  logout() {
    return request<undefined>("/api/v1/auth/logout", { method: "POST" })
  },
  products(params: ProductFilters = {}) {
    const search = new URLSearchParams()
    if (params.q) search.set("q", params.q)
    if (params.category_id) search.set("category_id", String(params.category_id))
    if (params.min_price !== undefined) search.set("min_price", String(params.min_price))
    if (params.max_price !== undefined) search.set("max_price", String(params.max_price))
    if (params.in_stock !== undefined) search.set("in_stock", String(params.in_stock))
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
}

/** All products across server pages. Aggregate use only, never for tables. */
export async function fetchAllProducts(): Promise<ProductOut[]> {
  const pageSize = 100
  const first = await api.products({ page: 1, page_size: pageSize })
  const all = [...first.items]
  let pageNum = 1
  while (all.length < first.total) {
    pageNum += 1
    const next = await api.products({ page: pageNum, page_size: pageSize })
    if (next.items.length === 0) break
    all.push(...next.items)
  }
  return all
}
