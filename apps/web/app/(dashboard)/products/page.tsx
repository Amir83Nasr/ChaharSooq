"use client"

import { useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { TablePagination } from "@workspace/ui/components/pagination"
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from "@workspace/ui/components/responsive-dialog"
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { EmptyState, ErrorState } from "@workspace/ui/components/state"
import { PackageSearch } from "lucide-react"
import {
  DataTableToolbar,
  SearchInput,
} from "@/components/data-table-toolbar"
import { PageHeader } from "@workspace/ui/components/page-header"
import { Price } from "@workspace/ui/components/price"
import { PersianDate } from "@workspace/ui/components/persian-date"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import {
  formatPersianNumber,
  parsePriceFilterInput,
} from "@workspace/ui/lib/number"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  api,
  ApiRequestError,
  fetchAllProducts,
  type CategoryOut,
  type ProductOut,
  type ProductPage,
  type ProductSort,
} from "@/lib/api"
import {
  STOCK_LABELS,
  stockStatus,
  summarizeInventory,
  type InventorySummary,
  type StockStatus,
} from "@/lib/inventory"

const PAGE_SIZES = [10, 20, 50]
const SEARCH_DEBOUNCE_MS = 400

type StockFilter = "all" | "in" | "out"

const SORT_LABELS: Record<ProductSort, string> = {
  newest: "جدیدترین",
  cheapest: "ارزان‌ترین",
  most_expensive: "گران‌ترین",
}

const STOCK_FILTER_LABELS: Record<StockFilter, string> = {
  all: "همه",
  in: "موجود",
  out: "ناموجود",
}

type StatColor = "emerald" | "red" | "sky"

const STAT_STYLES: Record<StatColor, { wrap: string; dot: string }> = {
  sky: {
    wrap: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
    dot: "bg-sky-500",
  },
  red: {
    wrap: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
    dot: "bg-red-500",
  },
  emerald: {
    wrap: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    dot: "bg-emerald-500",
  },
}

function StatBadge({ color, label, value }: { color: StatColor; label: string; value: number }) {
  const styles = STAT_STYLES[color]
  return (
    <span className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${styles.wrap}`}>
      <span aria-hidden="true" className="relative flex size-2 shrink-0">
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${styles.dot} opacity-60`} />
        <span className={`relative inline-flex size-2 rounded-full ${styles.dot}`} />
      </span>
      {label} <strong><PersianNumber value={value} /></strong>
    </span>
  )
}

function statusVariant(status: StockStatus): "secondary" | "default" | "destructive" {
  if (status === "out") return "destructive"
  if (status === "low") return "default"
  return "secondary"
}

export default function ProductsPage() {
  const router = useRouter()
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

  // Global catalog aggregate for the stats strip. Table errors/auth surface
  // through the paginated query below, so failures here stay silent.
  useEffect(() => {
    let cancelled = false
    fetchAllProducts()
      .then((all) => {
        if (!cancelled) setStats(summarizeInventory(all))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [catOpen])

  useEffect(() => {
    let cancelled = false
    setError(null)
    const min = minPrice.trim() === "" ? undefined : Number(minPrice)
    const max = maxPrice.trim() === "" ? undefined : Number(maxPrice)
    api
      .products({
        q: debouncedQ || undefined,
        category_id: categoryId ?? undefined,
        min_price: Number.isFinite(min) ? min : undefined,
        max_price: Number.isFinite(max) ? max : undefined,
        in_stock: stock === "all" ? undefined : stock === "in",
        sort,
        page: pageNum,
        page_size: pageSize,
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
  }, [goLogin, pageNum, pageSize, debouncedQ, categoryId, sort, stock, minPrice, maxPrice])

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

  const selectedStatus = selected ? stockStatus(selected.stock) : null

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
            <ResponsiveDialogContent aria-label="مدیریت دسته‌بندی‌ها">
              <ResponsiveDialogHeader>
                <ResponsiveDialogTitle>دسته‌بندی‌ها</ResponsiveDialogTitle>
                <ResponsiveDialogDescription>
                  دسته‌بندی جدید بسازید یا دسته‌بندی خالی را حذف کنید.
                </ResponsiveDialogDescription>
              </ResponsiveDialogHeader>
              <div className="flex items-center gap-2">
                <Input
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value)}
                  placeholder="نام دسته‌بندی جدید…"
                  aria-label="نام دسته‌بندی جدید"
                  maxLength={120}
                />
                <Button onClick={addCategory} disabled={!newCat.trim() || catBusy}>
                  افزودن
                </Button>
              </div>
              {catError ? <p role="alert" className="text-sm text-destructive">{catError}</p> : null}
              <ul className="flex flex-col gap-2">
                {categories.map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-2 rounded-md border border-border px-2.5 py-1.5">
                    <span>{c.name}</span>
                    <Button variant="ghost" size="sm" onClick={() => removeCategory(c.id)}>
                      حذف
                    </Button>
                  </li>
                ))}
                {categories.length === 0 ? (
                  <li className="text-sm text-muted-foreground">دسته‌بندی‌ای ثبت نشده است.</li>
                ) : null}
              </ul>
              <ResponsiveDialogFooter>
                <Button variant="outline" onClick={() => setCatOpen(false)}>
                  بستن
                </Button>
              </ResponsiveDialogFooter>
            </ResponsiveDialogContent>
          </ResponsiveDialog>
        }
      />

      {stats || page ? (
        <div className="mb-4 flex flex-wrap items-center gap-2" aria-label="آمار موجودی">
          <StatBadge color="sky" label="کل کالاها" value={stats?.total ?? 0} />
          <StatBadge color="red" label="کالاهای ناموجود" value={stats?.out ?? 0} />
          {hasFilters && page ? (
            <StatBadge color="emerald" label="نتایج فیلتر" value={page.total} />
          ) : null}
        </div>
      ) : null}

      <DataTableToolbar>
        <SearchInput
          value={q}
          onChange={(v) => {
            setQ(v)
            resetPage()
          }}
          placeholder="جست‌وجو در نام یا کد…"
          aria-label="جست‌وجو در محصولات"
        />
        <Select
          value={categoryId === null ? "all" : String(categoryId)}
          onValueChange={(v) => {
            setCategoryId(v === "all" ? null : Number(v))
            resetPage()
          }}
        >
          <SelectTrigger className="w-full sm:w-44" aria-label="فیلتر دسته‌بندی">
            <SelectValue>
              {(value: string | null) =>
                value === null || value === "all"
                  ? "همه دسته‌بندی‌ها"
                  : (categories.find((c) => String(c.id) === value)?.name ?? "همه دسته‌بندی‌ها")
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectGroup>
              <SelectLabel>دسته‌بندی</SelectLabel>
              <SelectItem value="all">همه دسته‌بندی‌ها</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Select
          value={sort}
          onValueChange={(v) => {
            setSort(v as ProductSort)
            resetPage()
          }}
        >
          <SelectTrigger className="w-full sm:w-44" aria-label="مرتب‌سازی">
            <SelectValue>
              {(value: ProductSort | null) =>
                value ? (SORT_LABELS[value] ?? "مرتب‌سازی") : "مرتب‌سازی"
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectGroup>
              <SelectLabel>مرتب‌سازی</SelectLabel>
              <SelectItem value="newest">جدیدترین</SelectItem>
              <SelectItem value="cheapest">ارزان‌ترین</SelectItem>
              <SelectItem value="most_expensive">گران‌ترین</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <Select
          value={stock}
          onValueChange={(v) => {
            setStock(v as StockFilter)
            resetPage()
          }}
        >
          <SelectTrigger className="w-full sm:w-44" aria-label="فیلتر موجودی">
            <SelectValue>
              {(value: StockFilter | null) =>
                value ? (STOCK_FILTER_LABELS[value] ?? "موجودی") : "موجودی"
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectGroup>
              <SelectLabel>موجودی</SelectLabel>
              <SelectItem value="all">همه</SelectItem>
              <SelectItem value="in">موجود</SelectItem>
              <SelectItem value="out">ناموجود</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <div className="relative w-full sm:w-40">
          <Input
            value={minPrice === "" ? "" : formatPersianNumber(minPrice)}
            onChange={(e) => {
              setMinPrice(parsePriceFilterInput(e.target.value))
              resetPage()
            }}
            placeholder="کمینه قیمت"
            aria-label="کمینه قیمت (تومان)"
            inputMode="numeric"
            className="w-full pe-12"
          />
          {minPrice !== "" ? (
            <span aria-hidden="true" className="pointer-events-none absolute inset-e-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
              تومان
            </span>
          ) : null}
        </div>
        <div className="relative w-full sm:w-40">
          <Input
            value={maxPrice === "" ? "" : formatPersianNumber(maxPrice)}
            onChange={(e) => {
              setMaxPrice(parsePriceFilterInput(e.target.value))
              resetPage()
            }}
            placeholder="بیشینه قیمت"
            aria-label="بیشینه قیمت (تومان)"
            inputMode="numeric"
            className="w-full pe-12"
          />
          {maxPrice !== "" ? (
            <span aria-hidden="true" className="pointer-events-none absolute inset-e-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
              تومان
            </span>
          ) : null}
        </div>
        {hasFilters ? (
          <Button variant="destructive" size="sm" onClick={clearFilters}>
            پاک‌سازی فیلترها
          </Button>
        ) : null}
      </DataTableToolbar>

      {error ? <ErrorState title="خطا در بارگذاری محصولات" hint={error} /> : null}
      {!page && !error ? (
        <div aria-label="در حال بارگذاری">
          <Table className="min-w-285 table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead>نام</TableHead>
                <TableHead className="text-center">کد</TableHead>
                <TableHead>دسته‌بندی</TableHead>
                <TableHead className="text-center">قیمت</TableHead>
                <TableHead className="text-center">موجودی</TableHead>
                <TableHead className="text-center">وضعیت</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j} className={j > 0 ? "text-center" : ""}>
                      <Skeleton
                        className={j > 0 ? "mx-auto h-4 w-20" : "h-4 w-20"}
                      />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
      {page && page.items.length === 0 ? (
        <EmptyState
          title={hasFilters ? "محصولی با این فیلترها یافت نشد" : "محصولی ثبت نشده است"}
          hint={hasFilters ? "فیلترها را تغییر دهید یا پاک کنید." : "اولین محصول را از طریق API اضافه کنید."}
          icon={<PackageSearch className="size-10 text-muted-foreground" />}
          action={
            hasFilters ? (
              <Button variant="destructive" size="sm" onClick={clearFilters}>
                پاک‌سازی فیلترها
              </Button>
            ) : undefined
          }
        />
      ) : null}
      {page && page.items.length > 0 ? (
        <div className="space-y-6">
          <Table className="min-w-285 table-fixed">
            <colgroup>
              <col className="w-44" />
              <col className="w-36" />
              <col className="w-52" />
              <col className="w-28" />
              <col className="w-24" />
              <col className="w-28" />
            </colgroup>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">نام</TableHead>
                <TableHead scope="col" className="text-center">کد</TableHead>
                <TableHead scope="col">دسته‌بندی</TableHead>
                <TableHead scope="col" className="text-center">قیمت</TableHead>
                <TableHead scope="col" className="text-center">موجودی</TableHead>
                <TableHead scope="col" className="text-center">وضعیت</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((item) => {
                const status = stockStatus(item.stock)
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
                    <TableCell>
                      <span className="text-sm font-medium">{item.name}</span>
                    </TableCell>
                    <TableCell className="text-center text-sm text-muted-foreground">
                      <span dir="ltr" className="inline-block">
                        {item.sku}
                      </span>
                    </TableCell>
                    <TableCell className="truncate">
                      {item.category ? <Badge variant="secondary">{item.category.name}</Badge> : <span className="text-muted-foreground">—</span>}
                    </TableCell>
                    <TableCell className="text-center">
                      <Price value={item.price} />
                    </TableCell>
                    <TableCell className="text-center">
                      <PersianNumber value={item.stock} />
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant={statusVariant(status)}>{STOCK_LABELS[status]}</Badge>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>

          <TablePagination
            page={pageNum}
            totalPages={totalPages}
            onPageChange={(p) =>
              setPageNum(Math.min(Math.max(1, p), totalPages))
            }
          >
            <Select
              value={String(pageSize)}
              onValueChange={(v) => {
                setPageSize(Number(v))
                resetPage()
              }}
            >
              <SelectTrigger size="sm" aria-label="تعداد محصول در هر صفحه">
                <SelectValue>
                  {(value: string | null) =>
                    value ? (
                      <span>
                        <PersianNumber value={Number(value)} /> محصول در صفحه
                      </span>
                    ) : (
                      "تعداد محصول در صفحه"
                    )
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent align="end">
                {PAGE_SIZES.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    <PersianNumber value={n} /> محصول در صفحه
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </TablePagination>
        </div>
      ) : null}

      <ResponsiveDialog open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null) }}>
        <ResponsiveDialogContent aria-label="جزئیات کالا">
          <ResponsiveDialogHeader>
            <ResponsiveDialogTitle>{selected?.name ?? ""}</ResponsiveDialogTitle>
            <ResponsiveDialogDescription>
              {selected ? `کد کالا: ${selected.sku}` : ""}
            </ResponsiveDialogDescription>
          </ResponsiveDialogHeader>
          {selected && selectedStatus ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge variant={statusVariant(selectedStatus)}>{STOCK_LABELS[selectedStatus]}</Badge>
                {selected.category ? (
                  <Badge variant="secondary">{selected.category.name}</Badge>
                ) : null}
              </div>
              <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div className="rounded-md border border-border px-3 py-2">
                  <dt className="text-xs text-muted-foreground">موجودی</dt>
                  <dd className="mt-0.5 font-semibold">
                    <PersianNumber value={selected.stock} /> عدد
                  </dd>
                </div>
                <div className="rounded-md border border-border px-3 py-2">
                  <dt className="text-xs text-muted-foreground">قیمت</dt>
                  <dd className="mt-0.5 font-semibold">
                    <Price value={selected.price} />
                  </dd>
                </div>
                <div className="rounded-md border border-border px-3 py-2">
                  <dt className="text-xs text-muted-foreground">ارزش قلم</dt>
                  <dd className="mt-0.5 font-semibold">
                    <Price value={selected.price * selected.stock} />
                  </dd>
                </div>
                <div className="rounded-md border border-border px-3 py-2">
                  <dt className="text-xs text-muted-foreground">دسته‌بندی</dt>
                  <dd className="mt-0.5 font-semibold">
                    {selected.category ? selected.category.name : "—"}
                  </dd>
                </div>
                <div className="rounded-md border border-border px-3 py-2">
                  <dt className="text-xs text-muted-foreground">کد</dt>
                  <dd className="mt-0.5 font-semibold">{selected.sku}</dd>
                </div>
                <div className="rounded-md border border-border px-3 py-2">
                  <dt className="text-xs text-muted-foreground">تاریخ ثبت</dt>
                  <dd className="mt-0.5 font-semibold">
                    <PersianDate value={selected.created_at} />
                  </dd>
                </div>
              </dl>
            </>
          ) : null}
        </ResponsiveDialogContent>
      </ResponsiveDialog>
    </>
  )
}
