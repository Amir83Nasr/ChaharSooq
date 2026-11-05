"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"
import { ArrowUpRight } from "lucide-react"

import { PageHeader } from "@workspace/ui/layout/page-header"
import { EmptyState, ErrorState } from "@workspace/ui/feedback/state"
import { Button, buttonVariants } from "@workspace/ui/primitives/button"
import { Card, CardContent } from "@workspace/ui/primitives/card"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"

import {
  api,
  ApiRequestError,
  GENERIC_ERROR_MESSAGE,
  type CompetitorGap,
  type ProductOut,
  type ProductPage,
} from "@/lib/api"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import { CompetitorSyncPanel } from "@/components/data/competitor-sync-panel"
import {
  DataTableToolbar,
  SearchInput,
} from "@/components/data/data-table-toolbar"
import { ProductDetailDialog } from "@/app/(dashboard)/products/_components/product-dialogs"
import { ProductsTable } from "@/app/(dashboard)/products/_components/products-table"
import type { AutoStoreKey } from "../../_components/store-config"

const SEARCH_DEBOUNCE_MS = 400
const GAPS_LIMIT = 5

function AutoStoreSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Card key={i}>
            <CardContent className="flex flex-col gap-2 p-5">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-4 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Skeleton className="h-64" />
    </div>
  )
}

export function AutoStoreView({
  store,
  storeName,
  description,
}: {
  store: AutoStoreKey
  storeName: string
  description: string
}) {
  const router = useRouter()
  const [page, setPage] = useState<ProductPage | null>(null)
  const [freshTotal, setFreshTotal] = useState(0)
  const [gaps, setGaps] = useState<CompetitorGap[]>([])
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ProductOut | null>(null)
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [pageNum, setPageNum] = useState(1)
  const [pageSize] = useState(10)
  const [onlyMissing, setOnlyMissing] = useState(false)
  const [dataVersion, setDataVersion] = useState(0)
  const [settingsLoaded, setSettingsLoaded] = useState(false)

  const refreshData = useCallback(() => setDataVersion((v) => v + 1), [])
  const goLogin = useCallback(() => {
    router.replace("/login")
    router.refresh()
  }, [router])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (cancelled) return
        if (Number.isFinite(data.low_stock_threshold)) {
          setThreshold(Math.max(0, Math.floor(data.low_stock_threshold)))
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
    Promise.all([
      api.products({
        q: debouncedQ || undefined,
        top_group: "لوازم خانگی",
        sort: "newest",
        page: pageNum,
        page_size: pageSize,
      }),
      api.products({
        top_group: "لوازم خانگی",
        competitor_store: store,
        page: 1,
        page_size: 1,
      }),
      api.dashboardGaps(50).catch((): CompetitorGap[] => []),
    ])
      .then(([table, fresh, allGaps]) => {
        if (cancelled) return
        if (table.page > 1 && table.items.length === 0) {
          setPageNum(Math.max(1, Math.ceil(table.total / table.page_size)))
          return
        }
        setPage(table)
        setFreshTotal(fresh.total)
        setGaps(
          allGaps
            .filter((gap) => gap.competitor_store === store)
            .slice(0, GAPS_LIMIT)
        )
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiRequestError && err.status === 401) {
          goLogin()
          return
        }
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
    store,
    dataVersion,
    settingsLoaded,
  ])

  const total = page?.total ?? 0
  const coverage = total > 0 ? Math.round((freshTotal / total) * 100) : 0
  const missing = Math.max(0, total - freshTotal)
  const totalPages = page
    ? Math.max(1, Math.ceil(page.total / page.page_size))
    : 1

  const visibleItems = onlyMissing
    ? (page?.items.filter((item) => {
        const competitor = item.competitor_prices.find(
          (price) => price.store === store
        )
        return competitor === undefined || competitor.is_fresh !== true
      }) ?? [])
    : (page?.items ?? [])
  const visiblePage: ProductPage | null =
    onlyMissing && page ? { ...page, items: visibleItems } : page

  return (
    <>
      <PageHeader
        title={`اتصال ${storeName}`}
        subtitle={description}
        actions={
          <CompetitorSyncPanel
            onSynced={refreshData}
            onUnauthorized={goLogin}
          />
        }
      />

      {error ? (
        <ErrorState
          title="خطا در بارگذاری اتصال"
          hint={error}
          action={<Button onClick={refreshData}>تلاش مجدد</Button>}
        />
      ) : page === null ? (
        <AutoStoreSkeleton />
      ) : total === 0 && debouncedQ === "" ? (
        <EmptyState
          title="کالای لوازم خانگی ثبت نشده است"
          hint="پس از همگام‌سازی با پارسبنا، کالاهای لوازم خانگی در این بخش نمایش داده می‌شوند."
          action={
            <Link
              href="/products"
              className={buttonVariants({ variant: "outline" })}
            >
              مشاهده محصولات
              <ArrowUpRight aria-hidden="true" />
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <p className="text-sm text-muted-foreground">
                  کالاهای لوازم خانگی
                </p>
                <p className="text-2xl font-bold">
                  <PersianNumber value={total} />
                </p>
                <p className="text-xs text-muted-foreground">
                  قلم فعال این گروه
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <p className="text-sm text-muted-foreground">پوشش قیمت تازه</p>
                <p className="text-2xl font-bold">
                  <PersianNumber value={coverage} />٪
                </p>
                <p className="text-xs text-muted-foreground">
                  <PersianNumber value={freshTotal} /> از{" "}
                  <PersianNumber value={total} /> قلم
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <p className="text-sm text-muted-foreground">
                  نیازمند لینک/بررسی
                </p>
                <p className="text-2xl font-bold">
                  <PersianNumber value={missing} />
                </p>
                <p className="text-xs text-muted-foreground">
                  بدون قیمت تازه {storeName}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <p className="text-sm text-muted-foreground">
                  بزرگ‌ترین اختلاف
                </p>
                {gaps.length === 0 ? (
                  <>
                    <p className="text-2xl font-bold">—</p>
                    <p className="text-xs text-muted-foreground">
                      مقایسه تازه‌ای ثبت نشده
                    </p>
                  </>
                ) : (
                  <>
                    <p
                      className="truncate text-sm font-semibold"
                      title={gaps[0]?.name}
                    >
                      {gaps[0]?.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      ما: {gaps[0] ? <Price value={gaps[0].our_price} /> : "—"}
                      {" — "}
                      {storeName}:{" "}
                      {gaps[0] ? (
                        <Price value={gaps[0].competitor_price} />
                      ) : (
                        "—"
                      )}
                    </p>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <DataTableToolbar>
            <SearchInput
              value={q}
              onChange={(v) => {
                setQ(v)
                setPageNum(1)
              }}
              placeholder="جست‌وجو در نام یا کد…"
              aria-label="جست‌وجو در کالاهای لوازم خانگی"
            />
            <Button
              variant={onlyMissing ? "default" : "outline"}
              size="sm"
              onClick={() => setOnlyMissing((v) => !v)}
              aria-pressed={onlyMissing}
            >
              فقط بدون قیمت تازه
            </Button>
          </DataTableToolbar>

          <ProductsTable
            page={visiblePage}
            threshold={threshold}
            pageNum={pageNum}
            totalPages={totalPages}
            pageSize={pageSize}
            showPageSize={false}
            hasFilters={debouncedQ !== "" || onlyMissing}
            market={store}
            onSelect={setSelected}
            onPageChange={(next) =>
              setPageNum(Math.min(Math.max(1, next), totalPages))
            }
            onPageSize={() => undefined}
          />
          <p className="text-xs leading-5 text-muted-foreground">
            برای ثبت یا بررسی لینک {storeName}، روی ردیف کالا بزنید تا جزئیات
            باز شود. قیمت فقط تا ۲۴ ساعت تازه محسوب می‌شود.
          </p>
        </div>
      )}

      <ProductDetailDialog
        selected={selected}
        onClose={() => setSelected(null)}
        onCompetitorChanged={refreshData}
      />
    </>
  )
}
