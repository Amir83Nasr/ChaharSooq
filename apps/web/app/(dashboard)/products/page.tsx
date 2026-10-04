"use client"

// NOTE: metadata lives in ./layout.tsx (client page cannot export it).

import { useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import {
  ResponsiveDialog,
  ResponsiveDialogTrigger,
} from "@workspace/ui/components/responsive-dialog"
import { PageHeader } from "@workspace/ui/components/page-header"
import { ErrorState } from "@workspace/ui/components/state"
import { useIsMobile } from "@workspace/ui/hooks/use-mobile"
import {
  api,
  ApiRequestError,
  type CategoryOut,
  type ProductOut,
  type ProductPage,
  type ProductSort,
} from "@/lib/api"
import {
  DEFAULT_LOW_STOCK_THRESHOLD,
  type InventorySummary,
} from "@/lib/inventory"
import { StatBadge } from "@/components/products-stat-badge"
import { CategoryDialog, ProductDetailDialog } from "./_components/product-dialogs"
import { ProductsTable } from "./_components/products-table"
import { ProductsToolbar, type StockFilter } from "./_components/products-toolbar"

const SEARCH_DEBOUNCE_MS = 400

export default function ProductsPage() {
  const router = useRouter()
  const isMobile = useIsMobile()
  const [page, setPage] = useState<ProductPage | null>(null)
  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<InventorySummary | null>(null)
  const [selected, setSelected] = useState<ProductOut | null>(null)

  const [pageNum, setPageNum] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [sort, setSort] = useState<ProductSort>("newest")
  const [stock, setStock] = useState<StockFilter>("all")
  const [minPrice, setMinPrice] = useState("")
  const [maxPrice, setMaxPrice] = useState("")
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)

  const [catOpen, setCatOpen] = useState(false)
  const [newCat, setNewCat] = useState("")
  const [catError, setCatError] = useState<string | null>(null)
  const [catBusy, setCatBusy] = useState(false)

  const goLogin = useCallback(() => {
    router.replace("/login")
    router.refresh()
  }, [router])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [q])

  const resetPage = useCallback(() => setPageNum(1), [])
  const effectivePageSize = isMobile ? 10 : pageSize

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
  }, [goLogin, catOpen])

  // Low-stock threshold + default page size come from server settings
  // so every device agrees.
  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (cancelled) return
        if (Number.isFinite(data.low_stock_threshold)) {
          setThreshold(Math.max(0, Math.floor(data.low_stock_threshold)))
        }
        if (data.default_page_size === 10 || data.default_page_size === 20 || data.default_page_size === 50) {
          setPageSize(data.default_page_size)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [catOpen])

  // Global catalog aggregate for the stats strip. Table errors/auth surface
  // through the paginated query below, so failures here stay silent.
  useEffect(() => {
    let cancelled = false
    api
      .productsSummary(threshold)
      .then((data) => {
        if (!cancelled) {
          const next: InventorySummary = {
            total: data.total,
            in: data.in_stock,
            low: data.low,
            out: data.out,
            stockValue: data.stock_value,
          }
          setStats(next)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [catOpen, threshold])

  useEffect(() => {
    let cancelled = false
    setError(null)
    const min = minPrice.trim() === "" ? undefined : Number(minPrice)
    const max = maxPrice.trim() === "" ? undefined : Number(maxPrice)
    const stockParams: { in_stock?: boolean; min_stock?: number; max_stock?: number } = {}
    if (stock === "in" || stock === "out") stockParams.in_stock = stock === "in"
    else if (stock === "low") {
      stockParams.in_stock = true
      stockParams.max_stock = threshold
    }
    api
      .products({
        q: debouncedQ || undefined,
        category_id: categoryId ?? undefined,
        min_price: Number.isFinite(min) ? min : undefined,
        max_price: Number.isFinite(max) ? max : undefined,
        ...stockParams,
        sort,
        page: pageNum,
        page_size: effectivePageSize,
      })
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiRequestError && err.status === 401) {
          goLogin()
          return
        }
        setError(err instanceof Error ? err.message : "خطایی رخ داد.")
      })
    return () => {
      cancelled = true
    }
  }, [goLogin, pageNum, effectivePageSize, debouncedQ, categoryId, sort, stock, threshold, minPrice, maxPrice])

  const totalPages = page ? Math.max(1, Math.ceil(page.total / page.page_size)) : 1
  const hasFilters =
    debouncedQ !== "" ||
    categoryId !== null ||
    stock !== "all" ||
    minPrice.trim() !== "" ||
    maxPrice.trim() !== ""

  function clearFilters() {
    setQ("")
    setDebouncedQ("")
    setCategoryId(null)
    setSort("newest")
    setStock("all")
    setMinPrice("")
    setMaxPrice("")
    setPageNum(1)
  }

  async function addCategory() {
    const name = newCat.trim()
    if (!name || catBusy) return
    setCatBusy(true)
    setCatError(null)
    try {
      await api.createCategory(name)
      setNewCat("")
    } catch (err: unknown) {
      setCatError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setCatBusy(false)
    }
  }

  async function removeCategory(id: number) {
    setCatError(null)
    try {
      await api.deleteCategory(id)
      setCategories((prev) => prev.filter((c) => c.id !== id))
      if (categoryId === id) {
        setCategoryId(null)
        resetPage()
      }
    } catch (err: unknown) {
      setCatError(err instanceof Error ? err.message : "خطایی رخ داد.")
    }
  }

  return (
    <>
      <PageHeader
        title="محصولات"
        subtitle="مدیریت کالاهای فروشگاه"
        actions={
          <ResponsiveDialog open={catOpen} onOpenChange={setCatOpen}>
            <ResponsiveDialogTrigger render={<Button variant="outline" />}>
              مدیریت دسته‌بندی‌ها
            </ResponsiveDialogTrigger>
            <CategoryDialog
              open={catOpen}
              categories={categories}
              newCat={newCat}
              catError={catError}
              catBusy={catBusy}
              onOpen={setCatOpen}
              onNewCat={setNewCat}
              onAdd={addCategory}
              onRemove={removeCategory}
              onClose={() => setCatOpen(false)}
            />
          </ResponsiveDialog>
        }
      />

      {stats || page ? (
        <div className="mb-4 flex flex-wrap items-center gap-2" aria-label="آمار موجودی">
          <StatBadge color="sky" label="کل کالاها" value={stats?.total ?? 0} />
          <StatBadge color="amber" label="موجودی کم" value={stats?.low ?? 0} />
          <StatBadge color="red" label="کالاهای ناموجود" value={stats?.out ?? 0} />
          {hasFilters && page ? (
            <StatBadge color="emerald" label="نتایج فیلتر" value={page.total} />
          ) : null}
        </div>
      ) : null}

      <ProductsToolbar
        q={q}
        categoryId={categoryId}
        categories={categories}
        sort={sort}
        stock={stock}
        minPrice={minPrice}
        maxPrice={maxPrice}
        hasFilters={hasFilters}
        onQ={(v) => {
          setQ(v)
          resetPage()
        }}
        onCategory={(v) => {
          setCategoryId(v)
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

      {error ? <ErrorState title="خطا در بارگذاری محصولات" hint={error} /> : null}
      {!page && !error ? <ProductsTable
        page={null}
        threshold={threshold}
        pageNum={pageNum}
        totalPages={totalPages}
        pageSize={pageSize}
        showPageSize={!isMobile}
        hasFilters={hasFilters}
        onSelect={setSelected}
        onPageChange={(p) => setPageNum(Math.min(Math.max(1, p), totalPages))}
        onPageSize={(n) => {
          setPageSize(n)
          resetPage()
        }}
      /> : null}
      {page ? <ProductsTable
        page={page}
        threshold={threshold}
        pageNum={pageNum}
        totalPages={totalPages}
        pageSize={pageSize}
        showPageSize={!isMobile}
        hasFilters={hasFilters}
        onSelect={setSelected}
        onPageChange={(p) => setPageNum(Math.min(Math.max(1, p), totalPages))}
        onPageSize={(n) => {
          setPageSize(n)
          resetPage()
        }}
      /> : null}

      <ProductDetailDialog
        selected={selected}
        threshold={threshold}
        onClose={() => setSelected(null)}
      />
    </>
  )
}
