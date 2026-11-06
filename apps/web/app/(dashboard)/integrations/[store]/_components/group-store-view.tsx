"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { ArrowUpRight } from "lucide-react"

import { PageHeader } from "@workspace/ui/layout/page-header"
import { EmptyState, ErrorState } from "@workspace/ui/feedback/state"
import { Button, buttonVariants } from "@workspace/ui/primitives/button"
import { Card, CardContent } from "@workspace/ui/primitives/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/primitives/table"
import { TablePagination } from "@workspace/ui/primitives/pagination"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"
import { formatPersianNumber } from "@workspace/ui/lib/number"

import {
  api,
  ApiRequestError,
  GENERIC_ERROR_MESSAGE,
  type DashboardOverview,
  type ProductOut,
  type ProductPage,
  type TopGroup,
} from "@/lib/api"
import { leaveToLogin } from "@/lib/auth-navigation"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import {
  DataTableToolbar,
  SearchInput,
} from "@/components/data/data-table-toolbar"
import { StockCell } from "@/components/data/products-stock-cell"
import { ProductDetailDialog } from "@/app/(dashboard)/products/_components/product-dialogs"
import {
  ProductsCards,
  ProductsMobileEmpty,
} from "@/app/(dashboard)/products/_components/products-cards"

const SEARCH_DEBOUNCE_MS = 400

function formatWeight(value: number): string {
  return formatPersianNumber(Math.round(value * 1000) / 1000)
}

function topBrandOf(name: string | null, top: TopGroup): string | null {
  if (!name) return null
  const n = name.trim()
  if (top === "فرش") {
    const rest = n.replace(/^فرش\s*/, "").trim()
    return rest || null
  }
  const rest = n.replace(/^مبلمان\s*/, "").trim()
  return rest || null
}

function GroupStoreSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
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

export function GroupStoreView({
  topGroup,
  storeName,
  description,
}: {
  topGroup: TopGroup
  storeName: string
  description: string
}) {
  const [page, setPage] = useState<ProductPage | null>(null)
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [weight, setWeight] = useState<number | null>(null)
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ProductOut | null>(null)
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [pageNum, setPageNum] = useState(1)
  const [dataVersion, setDataVersion] = useState(0)
  const [settingsLoaded, setSettingsLoaded] = useState(false)

  const refreshData = useCallback(() => setDataVersion((v) => v + 1), [])
  const goLogin = useCallback(() => {
    leaveToLogin()
  }, [])

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
        const formula = data.suggested_price_formulas.find(
          (f) => f.top_group === topGroup
        )
        setWeight(
          formula && Number.isFinite(formula.weight) ? formula.weight : null
        )
        setSettingsLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setSettingsLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [topGroup])

  useEffect(() => {
    if (!settingsLoaded) return
    let cancelled = false
    setError(null)
    Promise.all([
      api.products({
        q: debouncedQ || undefined,
        top_group: topGroup,
        sort: "newest",
        page: pageNum,
        page_size: 10,
      }),
      api
        .dashboardOverview(threshold)
        .catch((): DashboardOverview | null => null),
    ])
      .then(([table, overviewData]) => {
        if (cancelled) return
        if (table.page > 1 && table.items.length === 0) {
          setPageNum(Math.max(1, Math.ceil(table.total / table.page_size)))
          return
        }
        setPage(table)
        setOverview(overviewData)
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
    debouncedQ,
    topGroup,
    threshold,
    dataVersion,
    settingsLoaded,
  ])

  const total = page?.total ?? 0
  const groupValue = (overview?.groups ?? [])
    .filter((g) => g.name.trim().startsWith(topGroup))
    .reduce((sum, g) => sum + g.stock_value, 0)
  const totalPages = page
    ? Math.max(1, Math.ceil(page.total / page.page_size))
    : 1

  return (
    <>
      <PageHeader title={`اتصال ${storeName}`} subtitle={description} />

      {error ? (
        <ErrorState
          title="خطا در بارگذاری اتصال"
          hint={error}
          action={
            <Button onClick={refreshData} className="h-11 md:h-8">
              تلاش مجدد
            </Button>
          }
        />
      ) : page === null ? (
        <GroupStoreSkeleton />
      ) : total === 0 && debouncedQ === "" ? (
        <EmptyState
          title={`کالای ${topGroup} ثبت نشده است`}
          hint="پس از همگام‌سازی با پارسبنا، کالاهای این گروه در این بخش نمایش داده می‌شوند."
          action={
            <Link
              href="/products"
              className={buttonVariants({
                variant: "outline",
                className: "h-11 md:h-8",
              })}
            >
              مشاهده محصولات
              <ArrowUpRight aria-hidden="true" />
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2.5 sm:gap-4 xl:grid-cols-3">
            <Card>
              <CardContent className="flex flex-col gap-2 p-4 sm:p-5">
                <p className="text-sm text-muted-foreground">
                  کالاهای {topGroup}
                </p>
                <p className="text-xl font-bold sm:text-2xl">
                  <PersianNumber value={total} />
                </p>
                <p className="text-xs text-muted-foreground">
                  قلم فعال این گروه
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex flex-col gap-2 p-4 sm:p-5">
                <p className="text-sm text-muted-foreground">
                  ارزش موجودی گروه
                </p>
                {overview === null ? (
                  <Skeleton className="h-8 w-24" />
                ) : (
                  <>
                    <Price
                      value={groupValue}
                      className="text-xl font-bold sm:text-2xl"
                    />
                    <p className="text-xs text-muted-foreground">
                      مجموع قیمت × موجودی
                    </p>
                  </>
                )}
              </CardContent>
            </Card>
            <Card className="col-span-2 xl:col-span-1">
              <CardContent className="flex flex-col gap-2 p-4 sm:p-5">
                <p className="text-sm text-muted-foreground">
                  فرمول قیمت پیشنهادی {topGroup}
                </p>
                {weight === null ? (
                  <>
                    <p className="text-sm font-semibold">ثبت نشده است</p>
                    <Link
                      href="/settings/pricing"
                      className={buttonVariants({
                        variant: "outline",
                        size: "sm",
                      })}
                    >
                      ثبت وزن در تنظیمات
                      <ArrowUpRight aria-hidden="true" />
                    </Link>
                  </>
                ) : (
                  <>
                    <p className="text-sm leading-6 font-semibold">
                      {formatWeight(weight)} × قیمت رقیب +{" "}
                      {formatWeight(1 - weight)} × قیمت پارسینا
                    </p>
                    <Link
                      href="/settings/pricing"
                      className={buttonVariants({
                        variant: "outline",
                        size: "sm",
                      })}
                    >
                      ویرایش در تنظیمات
                      <ArrowUpRight aria-hidden="true" />
                    </Link>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <section className="space-y-1 rounded-2xl border border-dashed border-border bg-muted/40 p-4">
            <h2 className="font-semibold">مقایسه خودکار هنوز فعال نشده است</h2>
            <p className="text-sm leading-6 text-muted-foreground">
              استخراج خودکار قیمت فقط برای دیجی‌کالا و تکنولایف فعال است. برای{" "}
              {storeName} فعلا فهرست کالاهای {topGroup} را در همین صفحه ببینید و
              قیمت‌گذاری را با فرمول پیشنهادی تنظیمات پیش ببرید.
            </p>
          </section>

          <DataTableToolbar className="md:hidden">
            <SearchInput
              value={q}
              onChange={(v) => {
                setQ(v)
                setPageNum(1)
              }}
              placeholder="جست‌وجو در نام یا کد…"
              aria-label={`جست‌وجو در کالاهای ${topGroup}`}
              className="h-11 rounded-2xl"
            />
          </DataTableToolbar>
          <div className="hidden md:block">
            <DataTableToolbar>
              <SearchInput
                value={q}
                onChange={(v) => {
                  setQ(v)
                  setPageNum(1)
                }}
                placeholder="جست‌وجو در نام یا کد…"
                aria-label={`جست‌وجو در کالاهای ${topGroup}`}
              />
            </DataTableToolbar>
          </div>

          <div className="md:hidden">
            {page.items.length === 0 ? (
              <ProductsMobileEmpty hasFilters={debouncedQ !== ""} />
            ) : (
              <ProductsCards
                items={page.items}
                market="digikala"
                threshold={threshold}
                onSelect={setSelected}
              />
            )}
          </div>
          <div className="hidden md:block">
            <Table className="min-w-192 table-fixed">
              <colgroup>
                <col className="w-12" />
                <col className="w-64" />
                <col className="w-32" />
                <col className="w-40" />
                <col className="w-36" />
                <col className="w-28" />
              </colgroup>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col" className="text-center">
                    ردیف
                  </TableHead>
                  <TableHead scope="col">نام</TableHead>
                  <TableHead scope="col" className="text-center">
                    کد
                  </TableHead>
                  <TableHead scope="col">برند</TableHead>
                  <TableHead scope="col" className="text-center">
                    قیمت
                  </TableHead>
                  <TableHead scope="col" className="text-center">
                    موجودی
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {page.items.map((item, i) => {
                  const rowNumber =
                    (page.page > 1 ? (page.page - 1) * page.page_size : 0) +
                    i +
                    1
                  return (
                    <TableRow
                      key={item.id}
                      tabIndex={0}
                      className="cursor-pointer"
                      onClick={() => setSelected(item)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          setSelected(item)
                        }
                      }}
                    >
                      <TableCell className="text-center text-sm text-muted-foreground">
                        <PersianNumber value={rowNumber} />
                      </TableCell>
                      <TableCell className="wrap-break-word whitespace-normal">
                        <span className="text-sm font-medium">{item.name}</span>
                        {item.sub_group_name ? (
                          <span className="block truncate text-xs text-muted-foreground">
                            {item.sub_group_name}
                          </span>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-center text-sm text-muted-foreground">
                        <span
                          dir="ltr"
                          className="inline-block max-w-full truncate align-middle"
                        >
                          {item.sku}
                        </span>
                      </TableCell>
                      <TableCell className="truncate text-sm">
                        {topBrandOf(item.main_group_name, topGroup) ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        <Price value={item.price} />
                      </TableCell>
                      <TableCell className="text-center">
                        <StockCell value={item.stock} threshold={threshold} />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <TablePagination
            page={pageNum}
            totalPages={totalPages}
            onPageChange={(next) =>
              setPageNum(Math.min(Math.max(1, next), totalPages))
            }
          />
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
