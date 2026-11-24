"use client"

// NOTE: metadata lives in ./layout.tsx (client page cannot export it).

import { useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useMemo, useState } from "react"

import { ErrorState } from "@workspace/ui/feedback/state"
import { PageHeader } from "@workspace/ui/layout/page-header"
import { Button } from "@workspace/ui/primitives/button"

import {
  api,
  type ProductFilters,
  type ProductOut,
  type TopGroup,
} from "@/lib/api"
import { leaveToLogin } from "@/lib/auth-navigation"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import { normalizeProductTableColumns } from "@/lib/product-table-columns"
import {
  ensureProductsLoaded,
  getProductsSnapshot,
  primeProductsView,
  refreshProducts,
  resetProductsView,
  setProductsView,
  setSyncBaseline,
  useProductsStore,
  type StockFilter,
} from "@/lib/products-store"
import { toSuggestedPriceWeights } from "@/lib/suggested-price"
import { useSession } from "@/components/auth/session-provider"
import { ParsinaSyncPanel } from "@/components/data/parsina-sync-panel"
import { CompetitorSyncPanel } from "@/components/data/competitor-sync-panel"
import {
  ExportCsvMenu,
  type ExportCsvOption,
} from "@/components/data/export-csv-menu"
import { ProductDetailDialog } from "./_components/product-dialogs"
import {
  ProductsCards,
  ProductsMobileEmpty,
  ProductsMobilePagination,
  ProductsMobileSkeleton,
} from "./_components/products-cards"
import { ProductsMobileFilters } from "./_components/products-mobile-filters"
import { ProductsTable, ProductsTableError } from "./_components/products-table"
import { ProductsToolbar } from "./_components/products-toolbar"

const SEARCH_DEBOUNCE_MS = 400

function stockFromParam(value: string | null): StockFilter {
  return value === "in" || value === "out" || value === "low" ? value : "all"
}

function ProductsPageContent() {
  const searchParams = useSearchParams()
  const stockParam = searchParams.get("stock")
  const { canManage } = useSession()
  const { view, page, error, settings, syncBaseline } = useProductsStore()

  // Inputs are local so the caret never jumps; the store receives their
  // committed value after the debounce and keeps it across navigations.
  const [q, setQ] = useState(() => getProductsSnapshot().view.q)
  const [minPrice, setMinPrice] = useState(
    () => getProductsSnapshot().view.minPrice
  )
  const [maxPrice, setMaxPrice] = useState(
    () => getProductsSnapshot().view.maxPrice
  )
  const [selected, setSelected] = useState<ProductOut | null>(null)

  const goLogin = useCallback(() => leaveToLogin(), [])

  // Deep-linkable from the dashboard KPI cards (?stock=low / ?stock=out).
  // Prime it before the first fetch so the initial request carries the filter.
  useEffect(() => {
    if (stockParam !== null) {
      primeProductsView({ stock: stockFromParam(stockParam) })
    }
    void ensureProductsLoaded()
  }, [stockParam])

  useEffect(() => {
    const t = setTimeout(
      () => setProductsView({ q: q.trim() }),
      SEARCH_DEBOUNCE_MS
    )
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    const t = setTimeout(
      () => setProductsView({ minPrice }),
      SEARCH_DEBOUNCE_MS
    )
    return () => clearTimeout(t)
  }, [minPrice])

  useEffect(() => {
    const t = setTimeout(
      () => setProductsView({ maxPrice }),
      SEARCH_DEBOUNCE_MS
    )
    return () => clearTimeout(t)
  }, [maxPrice])

  const threshold = useMemo(() => {
    const value = settings?.low_stock_threshold
    return value !== undefined && Number.isFinite(value)
      ? Math.max(0, Math.floor(value))
      : DEFAULT_LOW_STOCK_THRESHOLD
  }, [settings])

  const weights = useMemo(
    () => toSuggestedPriceWeights(settings?.suggested_price_formulas ?? []),
    [settings]
  )

  const visibleColumns = useMemo(
    () => normalizeProductTableColumns(settings?.product_table_columns),
    [settings]
  )

  const totalPages = page
    ? view.pageSize === 0
      ? 1
      : Math.max(1, Math.ceil(page.total / Math.max(1, view.pageSize)))
    : 1

  const changePage = useCallback(
    (nextPage: number) =>
      setProductsView({
        page: Math.min(Math.max(1, nextPage), totalPages),
      }),
    [totalPages]
  )

  const changePageSize = useCallback((size: number) => {
    setProductsView({ pageSize: size, page: 1 })
  }, [])

  const hasFilters =
    q.trim() !== "" ||
    view.topGroup !== null ||
    view.sort !== "category" ||
    view.stock !== "all" ||
    view.market === "missing" ||
    minPrice.trim() !== "" ||
    maxPrice.trim() !== ""
  const activeFilterCount =
    (q.trim() !== "" ? 1 : 0) +
    (view.topGroup !== null ? 1 : 0) +
    (view.sort !== "category" ? 1 : 0) +
    (view.stock !== "all" ? 1 : 0) +
    (view.market === "missing" ? 1 : 0) +
    (minPrice.trim() !== "" ? 1 : 0) +
    (maxPrice.trim() !== "" ? 1 : 0)

  // "missing" is a filter only; column rendering still uses the "best" view.
  const displayMarket = view.market === "missing" ? "best" : view.market

  function clearFilters() {
    setQ("")
    setMinPrice("")
    setMaxPrice("")
    resetProductsView()
  }

  const filterProps = {
    q,
    topGroup: view.topGroup,
    sort: view.sort,
    stock: view.stock,
    market: view.market,
    minPrice,
    maxPrice,
    hasFilters,
    onQ: setQ,
    onTopGroup: (value: TopGroup | null) =>
      setProductsView({ topGroup: value }),
    onSort: (value: typeof view.sort) => setProductsView({ sort: value }),
    onStock: (value: StockFilter) => setProductsView({ stock: value }),
    onMarketChange: (value: typeof view.market) =>
      setProductsView({ market: value }),
    onMinPrice: setMinPrice,
    onMaxPrice: setMaxPrice,
    onClear: clearFilters,
  }

  const refreshFailed = error !== null && page !== null

  // Export uses the committed filters (the same view the table shows), not the
  // in-flight text inputs, so a half-typed search never shapes the file.
  const exportFilters = useMemo<ProductFilters>(() => {
    const toNumber = (value: string): number | undefined => {
      const trimmed = value.trim()
      if (!trimmed) return undefined
      const parsed = Number(trimmed)
      return Number.isFinite(parsed) ? parsed : undefined
    }
    const filters: ProductFilters = {
      q: view.q || undefined,
      top_group: view.topGroup ?? undefined,
      min_price: toNumber(view.minPrice),
      max_price: toNumber(view.maxPrice),
      ...(view.market === "missing"
        ? { pricing_mode: "no_competitor_price" as const }
        : view.market === "best"
          ? {}
          : { competitor_store: view.market }),
      sort: view.sort,
    }
    if (view.stock === "in" || view.stock === "out") {
      filters.in_stock = view.stock === "in"
    } else if (view.stock === "low") {
      filters.in_stock = true
      filters.max_stock = threshold
    }
    return filters
  }, [view, threshold])

  const exportOptions: ExportCsvOption[] = [
    {
      label: "خروجی نمای فعلی جدول",
      description: "ردیف‌های منطبق با فیلترها و ستون‌های نمایش‌داده‌شده",
      buildUrl: () =>
        api.productExportUrl(exportFilters, {
          columns: visibleColumns,
          market: displayMarket,
          scope: "filtered",
        }),
    },
    {
      label: "خروجی همه محصولات",
      description:
        "همهٔ ردیف‌ها بدون فیلتر، مرتب بر اساس دسته‌بندی، با ستون‌های نمایش‌داده‌شده",
      buildUrl: () =>
        api.productExportUrl(
          // The all-export drops the view filters; group rows by section instead
          // of using the API's newest-first default.
          { sort: "category" },
          { columns: visibleColumns, market: displayMarket, scope: "all" }
        ),
    },
  ]

  return (
    <>
      <PageHeader
        title="محصولات"
        subtitle="مدیریت کالاهای فروشگاه"
        actions={
          <>
            {/* Responsive visibility is CSS-only, so the server HTML already
                matches the device — no hydration-time swap that briefly shows
                the desktop toolbar (the full filter list) on mobile. */}
            <div className="hidden md:flex">
              <ExportCsvMenu options={exportOptions} onUnauthorized={goLogin} />
            </div>
            {canManage ? (
              <>
                <ParsinaSyncPanel
                  initialLastSuccess={syncBaseline.parsina}
                  onStatus={(value) => setSyncBaseline("parsina", value)}
                  onSynced={refreshProducts}
                  onUnauthorized={goLogin}
                />
                <CompetitorSyncPanel
                  initialLastSuccess={syncBaseline.competitor}
                  onStatus={(value) => setSyncBaseline("competitor", value)}
                  onSynced={refreshProducts}
                  onUnauthorized={goLogin}
                />
              </>
            ) : null}
          </>
        }
      />

      <div className="md:hidden">
        <ProductsMobileFilters
          {...filterProps}
          activeCount={activeFilterCount}
          exportMenu={
            <ExportCsvMenu
              compact
              options={exportOptions}
              onUnauthorized={goLogin}
            />
          }
        />
      </div>
      <div className="hidden md:block">
        <ProductsToolbar {...filterProps} />
      </div>

      {refreshFailed ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={refreshProducts}>
            تلاش مجدد
          </Button>
        </div>
      ) : null}

      {/* Both variants ship in the server HTML and CSS picks the right one.
          While data is loading the mobile branch is a skeleton instead of a
          live filter list, so a refresh never flashes full filters over an
          empty page before the cards arrive. */}
      <div className="md:hidden">
        {error !== null && page === null ? (
          <ErrorState
            title="خطا در بارگذاری محصولات"
            hint={error}
            action={<Button onClick={refreshProducts}>تلاش مجدد</Button>}
          />
        ) : page === null ? (
          <ProductsMobileSkeleton />
        ) : page.items.length === 0 ? (
          <ProductsMobileEmpty hasFilters={hasFilters} />
        ) : (
          <div className="space-y-4">
            <ProductsCards
              items={page.items}
              sort={view.sort}
              market={displayMarket}
              threshold={threshold}
              onSelect={setSelected}
            />
            <ProductsMobilePagination
              pageNum={view.page}
              totalPages={totalPages}
              onPageChange={changePage}
            />
          </div>
        )}
      </div>
      <div className="hidden md:block">
        {error !== null && page === null ? (
          <ProductsTableError
            message={error}
            onRetry={refreshProducts}
            visibleColumns={visibleColumns}
          />
        ) : (
          <ProductsTable
            page={page}
            threshold={threshold}
            pageNum={view.page}
            totalPages={totalPages}
            pageSize={view.pageSize}
            showPageSize
            hasFilters={hasFilters}
            sort={view.sort}
            market={displayMarket}
            weights={weights}
            visibleColumns={visibleColumns}
            onSelect={setSelected}
            onPageChange={changePage}
            onPageSize={changePageSize}
          />
        )}
      </div>

      <ProductDetailDialog
        selected={selected}
        onClose={() => setSelected(null)}
        onCompetitorChanged={refreshProducts}
        canEdit={canManage}
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
