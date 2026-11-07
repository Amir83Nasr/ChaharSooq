/* Client-side source of truth for the products table.

   The catalog is effectively static between syncs, so the page must not refetch
   on every mount. This module owns the view (filters/paging), the last valid
   response, and the settings snapshot; it lives outside React and therefore
   survives client navigations between routes.

   Refresh happens only when the data is explicitly invalidated (a sync run
   finished, a competitor price was edited, or the user retried) or when a view
   has never been loaded. A small per-query cache makes returning to a previous
   filter set instant too. */

import { useSyncExternalStore } from "react"

import {
  api,
  ApiRequestError,
  GENERIC_ERROR_MESSAGE,
  type DefaultCompetitorStore,
  type ProductFilters,
  type ProductPage,
  type ProductSort,
  type SettingsOut,
} from "./api"
import { buildProductParams } from "./api-params"
import { leaveToLogin } from "./auth-navigation"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "./inventory"

export type StockFilter = "all" | "in" | "out" | "low"

export interface ProductsView {
  q: string
  topGroup: string | null
  sort: ProductSort
  stock: StockFilter
  minPrice: string
  maxPrice: string
  page: number
  pageSize: number
  market: DefaultCompetitorStore
}

export type ProductsStatus = "idle" | "loading" | "refreshing"

export interface ProductsSyncBaseline {
  parsina: string | null
  competitor: string | null
}

export interface ProductsState {
  view: ProductsView
  settings: SettingsOut | null
  page: ProductPage | null
  status: ProductsStatus
  error: string | null
  syncBaseline: ProductsSyncBaseline
}

const INITIAL_VIEW: ProductsView = {
  q: "",
  topGroup: null,
  sort: "newest",
  stock: "all",
  minPrice: "",
  maxPrice: "",
  page: 1,
  pageSize: 0,
  market: "digikala",
}

/** Page-size values the settings endpoint accepts. */
const PAGE_SIZES = new Set([0, 10, 100, 500])

/** Last successful responses kept for instant back-and-forth between views. */
const CACHE_MAX = 3

function initialState(): ProductsState {
  return {
    view: { ...INITIAL_VIEW },
    settings: null,
    page: null,
    status: "idle",
    error: null,
    syncBaseline: { parsina: null, competitor: null },
  }
}

// Stable snapshot for the server render. The store is browser-only (it starts
// fetching in effects), so the server always sees the empty state.
const SERVER_STATE = initialState()

let state = initialState()
let pageCache = new Map<string, ProductPage>()
let loadedKey: string | null = null
let initialized = false
let dirty = false
let pageSizeUserSet = false
let marketUserSet = false
let requestSeq = 0
let inflight: { key: string; promise: Promise<void> } | null = null

const listeners = new Set<() => void>()

function emit(patch: Partial<ProductsState>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function getProductsSnapshot(): ProductsState {
  return state
}

function getServerSnapshot(): ProductsState {
  return SERVER_STATE
}

export function useProductsStore(): ProductsState {
  return useSyncExternalStore(subscribe, getProductsSnapshot, getServerSnapshot)
}

function threshold(): number {
  const value = state.settings?.low_stock_threshold
  if (value === undefined || !Number.isFinite(value)) {
    return DEFAULT_LOW_STOCK_THRESHOLD
  }
  return Math.max(0, Math.floor(value))
}

function priceParam(value: string): number | undefined {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : undefined
}

function paramsFromView(view: ProductsView): ProductFilters {
  const stockParams: Pick<ProductFilters, "in_stock" | "max_stock"> = {}
  if (view.stock === "in" || view.stock === "out") {
    stockParams.in_stock = view.stock === "in"
  } else if (view.stock === "low") {
    stockParams.in_stock = true
    stockParams.max_stock = threshold()
  }
  return {
    q: view.q || undefined,
    top_group: view.topGroup ?? undefined,
    min_price: priceParam(view.minPrice),
    max_price: priceParam(view.maxPrice),
    ...stockParams,
    sort: view.sort,
    page: view.page,
    page_size: view.pageSize,
  }
}

function keyFor(view: ProductsView): string {
  return buildProductParams(paramsFromView(view))
}

function cachePage(key: string, data: ProductPage): void {
  pageCache.delete(key)
  pageCache.set(key, data)
  while (pageCache.size > CACHE_MAX) {
    const oldest = pageCache.keys().next().value
    if (oldest === undefined) break
    pageCache.delete(oldest)
  }
}

function applySettings(settings: SettingsOut, initial: boolean): void {
  const previousView = state.view
  const previousKey = keyFor(previousView)
  const nextView = { ...previousView }

  if (
    (initial || !pageSizeUserSet) &&
    PAGE_SIZES.has(settings.default_page_size)
  ) {
    nextView.pageSize = settings.default_page_size
  }
  if (
    (initial || !marketUserSet) &&
    (settings.default_competitor_store === "digikala" ||
      settings.default_competitor_store === "technolife")
  ) {
    nextView.market = settings.default_competitor_store
  }

  emit({ settings, view: nextView })

  // A defaults change can alter the query (page size, low-stock threshold).
  // Only refetch from here on later mounts; the initial load is driven by
  // ensureProductsLoaded so a single request is issued.
  if (state.page !== null && keyFor(nextView) !== previousKey) {
    void fetchCurrent()
  }
}

async function loadSettings(initial: boolean): Promise<void> {
  try {
    const settings = await api.settings()
    applySettings(settings, initial)
  } catch {
    // Settings are display preferences. Defaults are already in place, so a
    // failed read must not block the catalog.
  }
}

function clearInflight(entry: { key: string; promise: Promise<void> }): void {
  if (inflight === entry) inflight = null
}

async function fetchCurrent(): Promise<void> {
  const view = state.view
  const key = keyFor(view)

  if (inflight && inflight.key === key) return inflight.promise

  const seq = ++requestSeq
  const entry: { key: string; promise: Promise<void> } = {
    key,
    promise: Promise.resolve(),
  }

  entry.promise = (async () => {
    emit({ status: state.page ? "refreshing" : "loading", error: null })
    try {
      const data = await api.products(paramsFromView(view))
      if (seq !== requestSeq) return
      // A sync can shrink the catalog; an emptied page falls back to the last.
      if (data.page > 1 && data.items.length === 0) {
        const lastPage = Math.max(
          1,
          Math.ceil(data.total / Math.max(1, data.page_size))
        )
        emit({ view: { ...state.view, page: lastPage } })
        clearInflight(entry)
        await fetchCurrent()
        return
      }
      cachePage(key, data)
      loadedKey = key
      dirty = false
      emit({ page: data, status: "idle", error: null })
    } catch (err: unknown) {
      if (seq !== requestSeq) return
      if (err instanceof ApiRequestError && err.status === 401) {
        leaveToLogin()
        return
      }
      // Keep the last table when a background refresh fails; the page shows a
      // non-blocking notice instead of replacing the data with an error state.
      emit({
        status: "idle",
        error:
          err instanceof ApiRequestError ? err.message : GENERIC_ERROR_MESSAGE,
      })
    } finally {
      clearInflight(entry)
    }
  })()

  inflight = entry
  return entry.promise
}

function currentKey(): string {
  return keyFor(state.view)
}

/**
 * Start a request that must not be coalesced with an already-running one.
 * Used after a sync/edit: the in-flight read may have started before the
 * change and would land stale.
 */
function forceFetch(): void {
  requestSeq += 1
  inflight = null
  void fetchCurrent()
}

function hasViewChanged(prev: ProductsView, next: ProductsView): boolean {
  return (
    prev.q !== next.q ||
    prev.topGroup !== next.topGroup ||
    prev.sort !== next.sort ||
    prev.stock !== next.stock ||
    prev.minPrice !== next.minPrice ||
    prev.maxPrice !== next.maxPrice ||
    prev.page !== next.page ||
    prev.pageSize !== next.pageSize ||
    prev.market !== next.market
  )
}

/**
 * Update the view. A changed query shows a cached response instantly when one
 * exists; otherwise the current table stays mounted while the new page loads.
 * The text inputs are committed by the page after its debounce, so this is not
 * called on every keystroke.
 */
export function setProductsView(patch: Partial<ProductsView>): void {
  const previous = state.view
  const next = { ...previous, ...patch }

  // Only a real value change resets paging; the debounced inputs re-send the
  // committed value on every mount and must not send the user back to page 1.
  const changesFilters =
    (patch.q !== undefined && patch.q !== previous.q) ||
    (patch.topGroup !== undefined && patch.topGroup !== previous.topGroup) ||
    (patch.sort !== undefined && patch.sort !== previous.sort) ||
    (patch.stock !== undefined && patch.stock !== previous.stock) ||
    (patch.minPrice !== undefined && patch.minPrice !== previous.minPrice) ||
    (patch.maxPrice !== undefined && patch.maxPrice !== previous.maxPrice) ||
    (patch.pageSize !== undefined && patch.pageSize !== previous.pageSize)

  // Any filter/page-size change returns to the first page unless the caller
  // explicitly picked one (paging itself).
  if (changesFilters && patch.page === undefined) next.page = 1

  if (
    patch.pageSize !== undefined &&
    patch.pageSize !== (state.settings?.default_page_size ?? 0)
  ) {
    pageSizeUserSet = true
  }
  if (
    patch.market !== undefined &&
    patch.market !== (state.settings?.default_competitor_store ?? "digikala")
  ) {
    marketUserSet = true
  }

  if (!hasViewChanged(previous, next)) return

  const nextKey = keyFor(next)
  if (nextKey === currentKey()) {
    emit({ view: next })
    return
  }

  const cached = pageCache.get(nextKey)
  if (cached) {
    loadedKey = nextKey
    dirty = false
    emit({ view: next, page: cached, status: "idle", error: null })
    return
  }

  emit({
    view: next,
    status: state.page ? "refreshing" : "loading",
    error: null,
  })
  void fetchCurrent()
}

/**
 * Update the view without issuing a fetch. Used for deep links that must be
 * applied before the initial request (so the first request already carries the
 * link filters instead of fetching twice).
 */
export function primeProductsView(patch: Partial<ProductsView>): void {
  const previous = state.view
  const next = { ...previous, ...patch }
  const changesFilters =
    (patch.q !== undefined && patch.q !== previous.q) ||
    (patch.topGroup !== undefined && patch.topGroup !== previous.topGroup) ||
    (patch.sort !== undefined && patch.sort !== previous.sort) ||
    (patch.stock !== undefined && patch.stock !== previous.stock) ||
    (patch.minPrice !== undefined && patch.minPrice !== previous.minPrice) ||
    (patch.maxPrice !== undefined && patch.maxPrice !== previous.maxPrice) ||
    (patch.pageSize !== undefined && patch.pageSize !== previous.pageSize)
  if (changesFilters && patch.page === undefined) next.page = 1
  if (!hasViewChanged(previous, next)) return
  emit({ view: next })
}

/** Restore the default view (settings defaults) and load it if needed. */
export function resetProductsView(): void {
  pageSizeUserSet = false
  marketUserSet = false
  const settings = state.settings
  const next: ProductsView = {
    ...INITIAL_VIEW,
    pageSize: PAGE_SIZES.has(settings?.default_page_size ?? 0)
      ? (settings?.default_page_size ?? 0)
      : 0,
    market: settings?.default_competitor_store ?? "digikala",
  }
  const previousKey = currentKey()
  const nextKey = keyFor(next)
  if (previousKey === nextKey) {
    emit({ view: next })
    return
  }
  const cached = pageCache.get(nextKey)
  if (cached) {
    loadedKey = nextKey
    dirty = false
    emit({ view: next, page: cached, status: "idle", error: null })
    return
  }
  emit({
    view: next,
    status: state.page ? "refreshing" : "loading",
    error: null,
  })
  void fetchCurrent()
}

/**
 * Load the page for the current view unless a valid response is already in
 * memory. Called on every mount of the products route.
 */
export async function ensureProductsLoaded(): Promise<void> {
  if (!initialized) {
    initialized = true
    if (!state.settings) {
      await loadSettings(true)
    }
  } else {
    // Cheap display-settings refresh; never blocks the table.
    void loadSettings(false)
  }

  if (
    !state.page ||
    dirty ||
    loadedKey !== currentKey() ||
    state.error !== null
  ) {
    await fetchCurrent()
  }
}

/** Force a fresh read of the current view (manual retry, sync, price edit). */
export function refreshProducts(): void {
  dirty = true
  pageCache = new Map()
  forceFetch()
}

/**
 * Mark the catalog stale. If the products route is mounted the current view is
 * refreshed in place; otherwise the next mount fetches once.
 */
export function invalidateProducts(): void {
  dirty = true
  pageCache = new Map()
  if (listeners.size > 0 && state.page !== null) {
    forceFetch()
  }
}

/**
 * Persist the last successful sync timestamp so the panels can detect a sync
 * that finished while the user was on another route. Initialising the panel's
 * baseline from here (instead of `null`) is what removes the blind reload.
 */
export function setSyncBaseline(
  source: keyof ProductsSyncBaseline,
  value: string | null
): void {
  if (state.syncBaseline[source] === value) return
  emit({ syncBaseline: { ...state.syncBaseline, [source]: value } })
}

/** Warm the catalog before the user clicks the sidebar link. */
export function prefetchProducts(): void {
  if (state.page !== null && !dirty) return
  void ensureProductsLoaded()
}

export function resetProductsStore(): void {
  requestSeq += 1
  inflight = null
  pageCache = new Map()
  loadedKey = null
  initialized = false
  dirty = false
  pageSizeUserSet = false
  marketUserSet = false
  state = initialState()
  for (const listener of listeners) listener()
}
