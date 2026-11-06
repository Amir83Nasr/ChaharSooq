import { memo } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/primitives/table"
import { TablePagination } from "@workspace/ui/primitives/pagination"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/primitives/select"
import { Button } from "@workspace/ui/primitives/button"
import { EmptyState } from "@workspace/ui/feedback/state"
import { Price } from "@workspace/ui/persian/price"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { formatPersianNumber } from "@workspace/ui/lib/number"
import { formatPersianRelativeTime } from "@workspace/ui/lib/relative-time"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { CircleAlert, PackageSearch, RefreshCw } from "lucide-react"
import { StockCell } from "@/components/data/products-stock-cell"
import { toTomanAmount } from "@/lib/money"
import type {
  ProductOut,
  ProductPage,
  ProductTableColumn,
  TopGroup,
} from "@/lib/api"
import {
  DEFAULT_PRODUCT_TABLE_COLUMNS,
  PRODUCT_TABLE_COLUMNS,
  productTableMinWidth,
} from "@/lib/product-table-columns"
import {
  suggestedPriceFor,
  type SuggestedPriceWeights,
} from "@/lib/suggested-price"
import { useWindowedRows, initialRowWindow } from "./use-windowed-rows"

import { PAGE_SIZE_OPTIONS } from "@/components/settings/page-size-settings"

interface TableProps {
  page: ProductPage | null
  threshold: number
  pageNum: number
  totalPages: number
  pageSize: number
  showPageSize: boolean
  hasFilters: boolean
  market: CompetitorMarket
  weights: SuggestedPriceWeights
  visibleColumns?: readonly ProductTableColumn[]
  onSelect: (item: ProductOut) => void
  onPageChange: (p: number) => void
  onPageSize: (n: number) => void
}

// Top-level groups for the catalog display: carpet, furniture, home appliances.
function topGroupOf(name: string | null): TopGroup | null {
  if (!name) return null
  const n = name.trim()
  if (n.startsWith("فرش")) return "فرش"
  if (n.startsWith("مبلمان")) return "مبلمان"
  return "لوازم خانگی"
}

// Brand is the remainder of the main group name after the top-level prefix.
function brandOf(name: string | null, top: string | null): string | null {
  if (!name) return null
  const n = name.trim()
  if (top === "فرش") {
    const rest = n.replace(/^فرش\s*/, "").trim()
    return rest || null
  }
  if (top === "مبلمان") {
    const rest = n.replace(/^مبلمان\s*/, "").trim()
    return rest || null
  }
  if (top === "لوازم خانگی") {
    const rest = n.replace(/^لوازم\s+خان[گک]ی\s*/, "").trim()
    return rest || n
  }
  return n
}

export type CompetitorMarket = "digikala" | "technolife"

export const COMPETITOR_MARKETS: { store: CompetitorMarket; label: string }[] =
  [
    { store: "digikala", label: "دیجی‌کالا" },
    { store: "technolife", label: "تکنولایف" },
  ]

const COMPETITOR_STATUS_LABELS: Record<string, string> = {
  pending: "در انتظار بررسی",
  success: "قیمت تازه دریافت نشده",
  not_found: "صفحه پیدا نشد",
  unavailable: "نیازمند بررسی",
  blocked: "دسترسی محدود شد",
  failed: "دریافت ناموفق",
  manual: "قیمت تازه ثبت نشده",
}

// اختلاف درصد قیمت ما نسبت به رقیب: مثبت یعنی گران‌تر از رقیب.
function diffPercent(ours: number, theirs: number | null): number | null {
  if (theirs === null || theirs <= 0 || ours <= 0) return null
  return ((ours - theirs) / theirs) * 100
}

function formatDiffPercent(diff: number): string {
  const rounded = Math.round(diff * 10) / 10
  const clean = Object.is(rounded, -0) ? 0 : rounded
  const absStr = Math.abs(clean).toFixed(1).replace(/\.0$/, "")
  return `${formatPersianNumber(absStr)}٪`
}

// Shared by the data, skeleton and error rows so the column layout never shifts.
// The competitor store is picked in the toolbar filters; the header only
// labels which store the column currently shows.
function ProductsTableHead(props: {
  market?: CompetitorMarket
  columns?: readonly ProductTableColumn[]
}) {
  const { market = "digikala", columns = DEFAULT_PRODUCT_TABLE_COLUMNS } = props
  const shown = new Set(columns)
  const marketLabel =
    COMPETITOR_MARKETS.find((m) => m.store === market)?.label ?? "دیجی‌کالا"
  return (
    <>
      <colgroup>
        {PRODUCT_TABLE_COLUMNS.filter((column) => shown.has(column.id)).map(
          (column) => (
            <col key={column.id} className={column.widthClass} />
          )
        )}
      </colgroup>
      <TableHeader>
        <TableRow>
          {shown.has("row") ? (
            <TableHead scope="col" className="text-center">
              ردیف
            </TableHead>
          ) : null}
          {shown.has("name") ? <TableHead scope="col">نام</TableHead> : null}
          {shown.has("sku") ? (
            <TableHead scope="col" className="text-center">
              کد
            </TableHead>
          ) : null}
          {shown.has("category") ? (
            <TableHead scope="col">دسته‌بندی</TableHead>
          ) : null}
          {shown.has("brand") ? <TableHead scope="col">برند</TableHead> : null}
          {shown.has("unit") ? (
            <TableHead scope="col" className="text-center">
              واحد
            </TableHead>
          ) : null}
          {shown.has("price") ? (
            <TableHead scope="col" className="text-center">
              قیمت
            </TableHead>
          ) : null}
          {shown.has("competitor_price") ? (
            <TableHead scope="col" className="text-center">
              <span className="inline-flex flex-col items-center gap-0.5">
                <span>قیمت رقبا</span>
                <span className="text-[11px] font-normal text-muted-foreground">
                  {marketLabel}
                </span>
              </span>
            </TableHead>
          ) : null}
          {shown.has("price_diff") ? (
            <TableHead scope="col" className="text-center">
              اختلاف درصد
            </TableHead>
          ) : null}
          {shown.has("suggested_price") ? (
            <TableHead scope="col" className="text-center">
              قیمت پیشنهادی
            </TableHead>
          ) : null}
          {shown.has("stock") ? (
            <TableHead scope="col" className="text-center">
              موجودی
            </TableHead>
          ) : null}
        </TableRow>
      </TableHeader>
    </>
  )
}

export function ProductTableSkeleton({
  columns = DEFAULT_PRODUCT_TABLE_COLUMNS,
}: {
  columns?: readonly ProductTableColumn[]
}) {
  const shown = new Set(columns)
  const visibleColumns = PRODUCT_TABLE_COLUMNS.filter((column) =>
    shown.has(column.id)
  )
  return (
    <div aria-label="در حال بارگذاری">
      <Table
        className="table-fixed"
        style={{ minWidth: productTableMinWidth(columns) }}
      >
        <ProductsTableHead columns={columns} />
        <TableBody>
          {Array.from({ length: 13 }).map((_, i) => (
            <TableRow key={i}>
              {visibleColumns.map((column) => (
                <TableCell
                  key={column.id}
                  className={column.center ? "text-center" : ""}
                >
                  <Skeleton
                    className={column.center ? "mx-auto h-4 w-20" : "h-4 w-20"}
                  />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// Zero-height-tolerant spacer for windowed rows (see useWindowedRows).
function SpacerRow({ height, colSpan }: { height: number; colSpan: number }) {
  return (
    <TableRow aria-hidden="true" className="border-0 hover:bg-transparent">
      <TableCell
        colSpan={colSpan}
        className="h-auto p-0"
        style={{ height, border: 0 }}
      />
    </TableRow>
  )
}

export const ProductsTable = memo(function ProductsTable(props: TableProps) {
  const {
    page,
    threshold,
    pageNum,
    totalPages,
    pageSize,
    showPageSize,
    hasFilters,
    market,
    weights,
    visibleColumns = DEFAULT_PRODUCT_TABLE_COLUMNS,
    onSelect,
    onPageChange,
    onPageSize,
  } = props
  const shown = new Set(visibleColumns)
  const columnCount = visibleColumns.length
  const marketLabel =
    COMPETITOR_MARKETS.find((m) => m.store === market)?.label ?? "دیجی‌کالا"
  // Windowed rendering (hooks before the early returns below): in "show all"
  // mode the whole catalog would otherwise stay mounted and every sidebar
  // toggle / theme flip would reflow thousands of rows.
  const { bodyRef, observeRow, win } = useWindowedRows(
    page?.items.length ?? 0,
    (i) => page?.items[i]?.id ?? i
  )
  if (!page) return <ProductTableSkeleton columns={visibleColumns} />
  if (page.items.length === 0) {
    return (
      <EmptyState
        title={
          hasFilters ? "محصولی با این فیلترها یافت نشد" : "محصولی ثبت نشده است"
        }
        hint={
          hasFilters
            ? "فیلترها را تغییر دهید یا پاک کنید."
            : "اولین محصول را از طریق API اضافه کنید."
        }
        icon={<PackageSearch className="size-10 text-muted-foreground" />}
      />
    )
  }
  // The window lags one frame behind a fresh fetch (new count, old window):
  // fall back to the deterministic initial window so the table never
  // flashes blank. The mount/scroll effects correct it right after.
  const count = page.items.length
  const renderWin =
    win.end > count || (win.end === 0 && count > 0)
      ? initialRowWindow(count)
      : win
  return (
    <div className="space-y-6">
      {pageSize === 0 && page.total > page.items.length ? (
        <p className="text-sm text-muted-foreground" role="status">
          {`از ${formatPersianNumber(page.total)} کالا، ${formatPersianNumber(page.items.length)} ردیف اول نمایش داده شد. برای دیدن بقیه از صفحه‌بندی یا فیلتر استفاده کنید.`}
        </p>
      ) : null}
      <Table
        className="table-fixed"
        style={{ minWidth: productTableMinWidth(visibleColumns) }}
        aria-rowcount={page.items.length}
      >
        <ProductsTableHead market={market} columns={visibleColumns} />
        <TableBody ref={bodyRef}>
          {renderWin.topPad > 0 ? (
            <SpacerRow height={renderWin.topPad} colSpan={columnCount} />
          ) : null}
          {page.items.slice(renderWin.start, renderWin.end).map((item, k) => {
            const i = renderWin.start + k
            const rowNumber =
              (page.page > 1
                ? (page.page - 1) * (page.page_size || page.items.length)
                : 0) +
              i +
              1
            const top = topGroupOf(item.main_group_name)
            const isAppliance = top === "لوازم خانگی"
            const competitor = isAppliance
              ? (item.competitor_prices.find(
                  (price) => price.store === market
                ) ?? null)
              : null
            const amount = toTomanAmount(
              competitor?.price ?? null,
              competitor?.currency ?? null
            )
            const pct =
              isAppliance && competitor?.is_fresh === true
                ? diffPercent(item.price, amount)
                : null
            const weight = top === null ? null : (weights[top] ?? null)
            const suggested =
              competitor?.is_fresh === true
                ? suggestedPriceFor(item.price, amount, weight)
                : null
            return (
              <TableRow
                key={item.id}
                tabIndex={0}
                aria-rowindex={i + 1}
                ref={observeRow(i)}
                className="cursor-pointer"
                onClick={() => onSelect(item)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    onSelect(item)
                  }
                }}
              >
                {shown.has("row") ? (
                  <TableCell className="text-center text-sm text-muted-foreground">
                    <PersianNumber value={rowNumber} />
                  </TableCell>
                ) : null}
                {shown.has("name") ? (
                  <TableCell className="wrap-break-word whitespace-normal">
                    <span className="text-sm font-medium">{item.name}</span>
                  </TableCell>
                ) : null}
                {shown.has("sku") ? (
                  <TableCell className="text-center text-sm text-muted-foreground">
                    <span
                      dir="ltr"
                      className="inline-block max-w-full truncate align-middle"
                    >
                      {item.sku}
                    </span>
                  </TableCell>
                ) : null}
                {shown.has("category") ? (
                  <TableCell className="text-center text-sm font-medium">
                    {top ?? <span className="text-muted-foreground">—</span>}
                  </TableCell>
                ) : null}
                {shown.has("brand") ? (
                  <TableCell className="whitespace-normal">
                    {brandOf(item.main_group_name, top) ? (
                      <>
                        <span className="block truncate text-sm">
                          {brandOf(item.main_group_name, top)}
                        </span>
                        {item.sub_group_name ? (
                          <span className="block truncate text-xs text-muted-foreground">
                            {item.sub_group_name}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                ) : null}
                {shown.has("unit") ? (
                  <TableCell className="truncate text-center text-sm">
                    {item.unit_name ?? (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                ) : null}
                {shown.has("price") ? (
                  <TableCell className="text-center">
                    <Price value={item.price} />
                  </TableCell>
                ) : null}
                {shown.has("competitor_price") ? (
                  <TableCell className="text-center">
                    {!isAppliance ? (
                      <span className="text-muted-foreground">—</span>
                    ) : competitor?.price !== null &&
                      competitor?.price !== undefined &&
                      amount !== null &&
                      amount !== undefined ? (
                      <span className="inline-flex flex-col items-center gap-0.5">
                        <Price value={amount} />
                        {!competitor.is_fresh ? (
                          <span
                            className="text-[11px] text-muted-foreground"
                            title={
                              competitor.last_checked_at
                                ? `آخرین بررسی: ${competitor.last_checked_at}`
                                : "قیمت تازه دریافت نشده"
                            }
                          >
                            {competitor.last_checked_at
                              ? (formatPersianRelativeTime(
                                  competitor.last_checked_at
                                ) ?? "قیمت قدیمی")
                              : "قیمت قدیمی"}
                          </span>
                        ) : null}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {competitor
                          ? (COMPETITOR_STATUS_LABELS[competitor.status] ??
                            "نیازمند بررسی")
                          : "لینک ثبت نشده"}
                      </span>
                    )}
                  </TableCell>
                ) : null}
                {shown.has("price_diff") ? (
                  <TableCell className="text-center">
                    {!isAppliance || pct === null ? (
                      <span className="text-muted-foreground">—</span>
                    ) : Object.is(Math.round(pct * 10) / 10, 0) || pct === 0 ? (
                      <span
                        className="block text-xs text-muted-foreground"
                        title={`${marketLabel}: بدون اختلاف`}
                      >
                        بدون اختلاف
                      </span>
                    ) : (
                      <span
                        className={`block text-xs font-medium ${
                          pct > 0 ? "text-destructive" : "text-success"
                        }`}
                        title={`${marketLabel}: ${formatDiffPercent(pct)} ${pct > 0 ? "گران‌تر" : "ارزان‌تر"} از رقیب`}
                      >
                        {formatDiffPercent(pct)}{" "}
                        {pct > 0 ? "گران‌تر" : "ارزان‌تر"}
                      </span>
                    )}
                  </TableCell>
                ) : null}
                {shown.has("suggested_price") ? (
                  <TableCell className="text-center">
                    {suggested === null ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <Price value={suggested} />
                    )}
                  </TableCell>
                ) : null}
                {shown.has("stock") ? (
                  <TableCell className="text-center">
                    <StockCell value={item.stock} threshold={threshold} />
                  </TableCell>
                ) : null}
              </TableRow>
            )
          })}
          {renderWin.bottomPad > 0 ? (
            <SpacerRow height={renderWin.bottomPad} colSpan={columnCount} />
          ) : null}
        </TableBody>
      </Table>
      <TablePagination
        page={pageNum}
        totalPages={totalPages}
        onPageChange={onPageChange}
      >
        {showPageSize ? (
          <Select
            value={String(pageSize)}
            onValueChange={(v) => onPageSize(Number(v))}
          >
            <SelectTrigger size="sm" aria-label="تعداد محصول در هر صفحه">
              <SelectValue>
                {(value: string | null) =>
                  value ? (
                    Number(value) === 0 ? (
                      <span>نمایش همه محصولات</span>
                    ) : (
                      <span>
                        <PersianNumber value={Number(value)} /> محصول در صفحه
                      </span>
                    )
                  ) : (
                    "تعداد محصول در صفحه"
                  )
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent align="end">
              {PAGE_SIZE_OPTIONS.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n === 0 ? (
                    <span>نمایش همه محصولات</span>
                  ) : (
                    <>
                      <PersianNumber value={n} /> محصول در صفحه
                    </>
                  )}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}
      </TablePagination>
    </div>
  )
})

interface TableErrorProps {
  message: string
  onRetry: () => void
  visibleColumns?: readonly ProductTableColumn[]
}

// Error state drawn inside the table itself, so it reads as "this table
// failed to load" instead of a detached card. Content is start-aligned on
// mobile: the table scrolls horizontally there and the start edge is the
// only part guaranteed to be on screen.
export function ProductsTableError({
  message,
  onRetry,
  visibleColumns = DEFAULT_PRODUCT_TABLE_COLUMNS,
}: TableErrorProps) {
  return (
    <Table
      className="table-fixed"
      style={{ minWidth: productTableMinWidth(visibleColumns) }}
    >
      <ProductsTableHead columns={visibleColumns} />
      <TableBody>
        <TableRow className="hover:bg-transparent">
          <TableCell
            colSpan={visibleColumns.length}
            className="whitespace-normal"
          >
            <div
              role="alert"
              className="flex max-w-sm flex-col items-start gap-3 py-8 md:mx-auto md:items-center md:text-center"
            >
              <span className="flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                <CircleAlert className="size-5" aria-hidden="true" />
              </span>
              <div className="space-y-1">
                <p className="text-sm font-semibold">خطا در بارگذاری محصولات</p>
                <p className="text-sm text-muted-foreground">{message}</p>
              </div>
              <Button variant="outline" size="sm" onClick={onRetry}>
                <RefreshCw aria-hidden="true" />
                تلاش مجدد
              </Button>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  )
}
