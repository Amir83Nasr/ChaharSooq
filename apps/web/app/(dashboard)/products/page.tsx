"use client"

// NOTE: metadata lives in ./layout.tsx (client page cannot export it).

import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useState } from "react"

import { PageHeader } from "@workspace/ui/layout/page-header"
import {
  api,
  ApiRequestError,
  GENERIC_ERROR_MESSAGE,
  type CategoryOut,
  type DefaultCompetitorStore,
  type ProductOut,
  type ProductPage,
  type ProductSort,
  type ProductTableColumn,
} from "@/lib/api"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import {
  DEFAULT_PRODUCT_TABLE_COLUMNS,
  normalizeProductTableColumns,
} from "@/lib/product-table-columns"
import {
  toSuggestedPriceWeights,
  type SuggestedPriceWeights,
} from "@/lib/suggested-price"
import { ParsinaSyncPanel } from "@/components/data/parsina-sync-panel"
import { CompetitorSyncPanel } from "@/components/data/competitor-sync-panel"
import { ProductDetailDialog } from "./_components/product-dialogs"
import {
  ProductsCards,
  ProductsMobileEmpty,
  ProductsMobilePagination,
  ProductsMobileSkeleton,
} from "./_components/products-cards"
import { ProductsMobileFilters } from "./_components/products-mobile-filters"
import { ProductsTable, ProductsTableError } from "./_components/products-table"
import {
  ProductsToolbar,
  type StockFilter,
} from "./_components/products-toolbar"

const SEARCH_DEBOUNCE_MS = 400

function stockFromParam(value: string | null): StockFilter {
  return value === "in" || value === "out" || value === "low" ? value : "all"
}

function ProductsPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [page, setPage] = useState<ProductPage | null>(null)
  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ProductOut | null>(null)

  const [pageNum, setPageNum] = useState(1)
  const [pageSize, setPageSize] = useState(0)
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [topGroup, setTopGroup] = useState<string | null>(null)
  const [sort, setSort] = useState<ProductSort>("newest")
  // Deep-linkable from the dashboard KPI cards (?stock=low / ?stock=out).
  const [stock, setStock] = useState<StockFilter>(() =>
    stockFromParam(searchParams.get("stock"))
  )
  const [minPrice, setMinPrice] = useState("")
  const [maxPrice, setMaxPrice] = useState("")
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)
  const [market, setMarket] = useState<DefaultCompetitorStore>("digikala")
  const [weights, setWeights] = useState<SuggestedPriceWeights>({})
  // Visible product-table columns come from the admin settings; hidden
  // columns are skipped so the remaining ones keep their width.
  const [visibleColumns, setVisibleColumns] = useState<ProductTableColumn[]>([
    ...DEFAULT_PRODUCT_TABLE_COLUMNS,
  ])
  // Bumped after a sync lands — re-fetches table + stats in place, keeping
  // search/sort/paging state untouched.
  const [dataVersion, setDataVersion] = useState(0)
  const refreshData = useCallback(() => setDataVersion((v) => v + 1), [])
  // Auto-refresh cadence follows the configured sync interval.
  const [autoRefreshMs, setAutoRefreshMs] = useState(24 * 60 * 60 * 1000)
  // Gates the product query until server settings resolve, so a reload
  // issues one product request (with the real threshold/page size) instead
  // of flashing an intermediate result fetched with local defaults.
  const [settingsLoaded, setSettingsLoaded] = useState(false)

  useEffect(() => {
    if (!autoRefreshMs || autoRefreshMs <= 0) return
    let id: ReturnType<typeof setInterval> | undefined
    const start = () => {
      if (id !== undefined) return
      id = setInterval(() => setDataVersion((v) => v + 1), autoRefreshMs)
    }
    const stop = () => {
      if (id !== undefined) {
        clearInterval(id)
        id = undefined
      }
    }
    const onVisibility = () => {
      if (document.hidden) stop()
      else start()
    }
    start()
    document.addEventListener("visibilitychange", onVisibility)
    return () => {
      stop()
      document.removeEventListener("visibilitychange", onVisibility)
    }
  }, [autoRefreshMs])

  const goLogin = useCallback(() => {
    router.replace("/login")
    router.refresh()
  }, [router])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [q])

  const resetPage = useCallback(() => setPageNum(1), [])

  useEffect(() => {
    let cancelled = false
    api
      .categories()
      .then((data) => {
        if (!cancelled) setCategories(data)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiRequestError && err.status === 401) {
          goLogin()
          return
        }
      })
    return () => {
      cancelled = true
    }
  }, [goLogin])

  // Low-stock threshold + default page size + default competitor market come
  // from server settings so every device agrees.
  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (cancelled) return
        if (Number.isFinite(data.low_stock_threshold)) {
          setThreshold(Math.max(0, Math.floor(data.low_stock_threshold)))
        }
        if (
          data.default_page_size === 0 ||
          data.default_page_size === 10 ||
          data.default_page_size === 100 ||
          data.default_page_size === 500
        ) {
          setPageSize(data.default_page_size)
        }
        if (
          data.default_competitor_store === "digikala" ||
          data.default_competitor_store === "technolife"
        ) {
          setMarket(data.default_competitor_store)
        }
        setWeights(toSuggestedPriceWeights(data.suggested_price_formulas))
        setVisibleColumns(
          normalizeProductTableColumns(data.product_table_columns)
        )
        if (Number.isFinite(data.sync_interval_minutes)) {
          const ms =
            Math.max(1, Math.floor(data.sync_interval_minutes)) * 60 * 1000
          setAutoRefreshMs(ms)
        }
        setSettingsLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setSettingsLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!settingsLoaded) return
    let cancelled = false
    setError(null)
    const min = minPrice.trim() === "" ? undefined : Number(minPrice)
    const max = maxPrice.trim() === "" ? undefined : Number(maxPrice)
    const stockParams: {
      in_stock?: boolean
      min_stock?: number
      max_stock?: number
    } = {}
    if (stock === "in" || stock === "out") stockParams.in_stock = stock === "in"
    else if (stock === "low") {
      stockParams.in_stock = true
      stockParams.max_stock = threshold
    }
    api
      .products({
        q: debouncedQ || undefined,
        top_group: topGroup ?? undefined,
        min_price: Number.isFinite(min) ? min : undefined,
        max_price: Number.isFinite(max) ? max : undefined,
        ...stockParams,
        sort,
        page: pageNum,
        page_size: pageSize,
      })
      .then((data) => {
        if (cancelled) return
        // A sync can shrink the catalog; an emptied page falls back to the last one.
        if (data.page > 1 && data.items.length === 0) {
          setPageNum(Math.max(1, Math.ceil(data.total / data.page_size)))
          return
        }
        setPage(data)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiRequestError && err.status === 401) {
          goLogin()
          return
        }
        // Only ApiRequestError messages are Persian-safe; anything else (e.g.
        // a JSON parse failure) would surface a raw English message.
        setError(
          err instanceof ApiRequestError ? err.message : GENERIC_ERROR_MESSAGE
        )
      })
    return () => {
      cancelled = true
    }
  }, [
    goLogin,
    pageNum,
    pageSize,
    debouncedQ,
    topGroup,
    sort,
    stock,
    threshold,
    minPrice,
    maxPrice,
    dataVersion,
    settingsLoaded,
  ])

  const totalPages = page
    ? pageSize === 0
      ? 1
      : Math.max(1, Math.ceil(page.total / page.page_size))
    : 1
  const changePage = useCallback(
    (nextPage: number) =>
      setPageNum(Math.min(Math.max(1, nextPage), totalPages)),
    [totalPages]
  )
  const changePageSize = useCallback(
    (size: number) => {
      setPageSize(size)
      resetPage()
    },
    [resetPage]
  )
  const hasFilters =
    debouncedQ !== "" ||
    topGroup !== null ||
    sort !== "newest" ||
    stock !== "all" ||
    minPrice.trim() !== "" ||
    maxPrice.trim() !== ""
  const activeFilterCount =
    (debouncedQ !== "" ? 1 : 0) +
    (topGroup !== null ? 1 : 0) +
    (sort !== "newest" ? 1 : 0) +
    (stock !== "all" ? 1 : 0) +
    (minPrice.trim() !== "" ? 1 : 0) +
    (maxPrice.trim() !== "" ? 1 : 0)

  function clearFilters() {
    setQ("")
    setDebouncedQ("")
    setTopGroup(null)
    setSort("newest")
    setStock("all")
    setMinPrice("")
    setMaxPrice("")
    setPageNum(1)
  }

  return (
    <>
      <PageHeader
        title="محصولات"
        subtitle="مدیریت کالاهای فروشگاه"
        actions={
          <>
            <ParsinaSyncPanel onSynced={refreshData} onUnauthorized={goLogin} />
            <CompetitorSyncPanel
              onSynced={refreshData}
              onUnauthorized={goLogin}
            />
          </>
        }
      />

      <ProductsMobileFilters
        q={q}
        topGroup={topGroup}
        sort={sort}
        stock={stock}
        market={market}
        minPrice={minPrice}
        maxPrice={maxPrice}
        hasFilters={hasFilters}
        activeCount={activeFilterCount}
        onQ={(v) => {
          setQ(v)
          resetPage()
        }}
        onTopGroup={(v) => {
          setTopGroup(v)
          resetPage()
        }}
        onSort={(v) => {
          setSort(v)
          resetPage()
        }}
        onStock={(v) => {
          setStock(v)
          resetPage()
        }}
        onMarketChange={setMarket}
        onMinPrice={(v) => {
          setMinPrice(v)
          resetPage()
        }}
        onMaxPrice={(v) => {
          setMaxPrice(v)
          resetPage()
        }}
        onClear={clearFilters}
      />

      <div className="hidden md:block">
        <ProductsToolbar
          q={q}
          topGroup={topGroup}
          sort={sort}
          stock={stock}
          market={market}
          minPrice={minPrice}
          maxPrice={maxPrice}
          hasFilters={hasFilters}
          onQ={(v) => {
            setQ(v)
            resetPage()
          }}
          onTopGroup={(v) => {
            setTopGroup(v)
            resetPage()
          }}
          onSort={(v) => {
            setSort(v)
            resetPage()
          }}
          onStock={(v) => {
            setStock(v)
            resetPage()
          }}
          onMarketChange={setMarket}
          onMinPrice={(v) => {
            setMinPrice(v)
            resetPage()
          }}
          onMaxPrice={(v) => {
            setMaxPrice(v)
            resetPage()
          }}
          onClear={clearFilters}
        />
      </div>

      {error ? (
        <ProductsTableError
          message={error}
          onRetry={refreshData}
          visibleColumns={visibleColumns}
        />
      ) : (
        <>
          <div className="md:hidden">
            {page === null ? (
              <ProductsMobileSkeleton />
            ) : page.items.length === 0 ? (
              <ProductsMobileEmpty hasFilters={hasFilters} />
            ) : (
              <div className="space-y-4">
                <ProductsCards
                  items={page.items}
                  market={market}
                  threshold={threshold}
                  onSelect={setSelected}
                />
                <ProductsMobilePagination
                  pageNum={pageNum}
                  totalPages={totalPages}
                  onPageChange={changePage}
                />
              </div>
            )}
          </div>
          <div className="hidden md:block">
            <ProductsTable
              page={page}
              threshold={threshold}
              pageNum={pageNum}
              totalPages={totalPages}
              pageSize={pageSize}
              showPageSize
              hasFilters={hasFilters}
              market={market}
              weights={weights}
              visibleColumns={visibleColumns}
              onSelect={setSelected}
              onPageChange={changePage}
              onPageSize={changePageSize}
            />
          </div>
        </>
      )}

      <ProductDetailDialog
        selected={selected}
        onClose={() => setSelected(null)}
        onCompetitorChanged={refreshData}
      />
    </>
  )
}

// useSearchParams needs a Suspense boundary for static prerendering.
export default function ProductsPage() {
  return (
    <Suspense>
      <ProductsPageContent />
    </Suspense>
  )
}
