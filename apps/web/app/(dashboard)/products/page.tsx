"use client"

// NOTE: metadata lives in ./layout.tsx (client page cannot export it).

import { useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"

import { PageHeader } from "@workspace/ui/components/page-header"
import { useIsMobile } from "@workspace/ui/hooks/use-mobile"
import {
  api,
  ApiRequestError,
  GENERIC_ERROR_MESSAGE,
  type CategoryOut,
  type DefaultCompetitorStore,
  type ProductOut,
  type ProductPage,
  type ProductSort,
} from "@/lib/api"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import { ParsinaSyncPanel } from "@/components/parsina-sync-panel"
import { ProductDetailDialog } from "./_components/product-dialogs"
import { ProductsTable, ProductsTableError } from "./_components/products-table"
import {
  ProductsToolbar,
  type StockFilter,
} from "./_components/products-toolbar"

const SEARCH_DEBOUNCE_MS = 400

export default function ProductsPage() {
  const router = useRouter()
  const isMobile = useIsMobile()
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
  const [stock, setStock] = useState<StockFilter>("all")
  const [minPrice, setMinPrice] = useState("")
  const [maxPrice, setMaxPrice] = useState("")
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)
  const [market, setMarket] = useState<DefaultCompetitorStore>("digikala")
  // Bumped after a sync lands — re-fetches table + stats in place, keeping
  // search/sort/paging state untouched.
  const [dataVersion, setDataVersion] = useState(0)
  const refreshData = useCallback(() => setDataVersion((v) => v + 1), [])
  // Auto-refresh cadence follows the configured sync interval (minutes).
  const [autoRefreshMs, setAutoRefreshMs] = useState(60 * 60 * 1000)

  useEffect(() => {
    if (!autoRefreshMs || autoRefreshMs <= 0) return
    const id = setInterval(() => setDataVersion((v) => v + 1), autoRefreshMs)
    return () => clearInterval(id)
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
  const effectivePageSize = isMobile ? 0 : pageSize
  useEffect(() => {
    resetPage()
  }, [isMobile, resetPage])

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
        if (Number.isFinite(data.sync_interval_minutes)) {
          const ms =
            Math.max(1, Math.floor(data.sync_interval_minutes)) * 60 * 1000
          setAutoRefreshMs(ms)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
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
        page_size: effectivePageSize,
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
    effectivePageSize,
    debouncedQ,
    topGroup,
    sort,
    stock,
    threshold,
    minPrice,
    maxPrice,
    dataVersion,
  ])

  const totalPages = page
    ? Math.max(1, Math.ceil(page.total / page.page_size))
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
    stock !== "all" ||
    minPrice.trim() !== "" ||
    maxPrice.trim() !== ""

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
          <ParsinaSyncPanel onSynced={refreshData} onUnauthorized={goLogin} />
        }
      />

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

      {error ? (
        <ProductsTableError message={error} onRetry={refreshData} />
      ) : (
        <ProductsTable
          page={page}
          threshold={threshold}
          pageNum={pageNum}
          totalPages={totalPages}
          pageSize={pageSize}
          showPageSize={!isMobile}
          hasFilters={hasFilters}
          market={market}
          onSelect={setSelected}
          onPageChange={changePage}
          onPageSize={changePageSize}
        />
      )}

      <ProductDetailDialog
        selected={selected}
        onClose={() => setSelected(null)}
      />
    </>
  )
}
