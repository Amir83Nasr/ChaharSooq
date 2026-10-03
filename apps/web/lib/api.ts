/* Typed fetch client for the Charsooq FastAPI contract (OpenAPI-derived shapes). */

export interface ProductOut {
  id: number
  name: string
  sku: string
  price: number
  stock: number
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

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiError | null
    throw new Error(body?.error.message ?? `درخواست ناموفق بود (${res.status})`)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
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
  products(params: { q?: string; page?: number; page_size?: number } = {}) {
    const search = new URLSearchParams()
    if (params.q) search.set("q", params.q)
    if (params.page) search.set("page", String(params.page))
    if (params.page_size) search.set("page_size", String(params.page_size))
    const suffix = search.size ? `?${search}` : ""
    return request<ProductPage>(`/api/v1/products${suffix}`)
  },
}
