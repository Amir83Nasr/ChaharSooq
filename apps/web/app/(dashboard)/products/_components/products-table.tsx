import { memo } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { TablePagination } from "@workspace/ui/components/pagination"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Button } from "@workspace/ui/components/button"
import { EmptyState } from "@workspace/ui/components/state"
import { Price } from "@workspace/ui/components/price"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { CircleAlert, PackageSearch, RefreshCw } from "lucide-react"
import { StockCell } from "@/components/products-stock-cell"
import type { ProductOut, ProductPage } from "@/lib/api"

import { PAGE_SIZE_OPTIONS } from "@/components/page-size-settings"

interface TableProps {
  page: ProductPage | null
  threshold: number
  pageNum: number
  totalPages: number
  pageSize: number
  showPageSize: boolean
  hasFilters: boolean
  onSelect: (item: ProductOut) => void
  onPageChange: (p: number) => void
  onPageSize: (n: number) => void
}

const COLUMN_COUNT = 11

// Top-level groups for the catalog display: carpet, furniture, home appliances.
function topGroupOf(name: string | null): string | null {
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

// Shared by the data, skeleton and error rows so the column layout never shifts.
function ProductsTableHead() {
  return (
    <>
      <colgroup>
        <col className="w-12" />
        <col className="w-56" />
        <col className="w-32" />
        <col className="w-24" />
        <col className="w-40" />
        <col className="w-20" />
        <col className="w-28" />
        <col className="w-28" />
        <col className="w-20" />
        <col className="w-24" />
        <col className="w-24" />
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
          <TableHead scope="col">دسته‌بندی</TableHead>
          <TableHead scope="col">برند</TableHead>
          <TableHead scope="col" className="text-center">
            واحد
          </TableHead>
          <TableHead scope="col" className="text-center">
            قیمت
          </TableHead>
          <TableHead scope="col" className="text-center">
            قیمت رقبا
          </TableHead>
          <TableHead scope="col" className="text-center">
            اختلاف درصد
          </TableHead>
          <TableHead scope="col" className="text-center">
            تغییرات قیمت
          </TableHead>
          <TableHead scope="col" className="text-center">
            موجودی
          </TableHead>
        </TableRow>
      </TableHeader>
    </>
  )
}

export function ProductTableSkeleton() {
  return (
    <div aria-label="در حال بارگذاری">
      <Table className="min-w-212 table-fixed">
        <ProductsTableHead />
        <TableBody>
          {Array.from({ length: 5 }).map((_, i) => (
            <TableRow key={i}>
              {Array.from({ length: COLUMN_COUNT }).map((_, j) => {
                const centered = j === 0 || j === 2 || j >= 5
                return (
                  <TableCell key={j} className={centered ? "text-center" : ""}>
                    <Skeleton
                      className={centered ? "mx-auto h-4 w-20" : "h-4 w-20"}
                    />
                  </TableCell>
                )
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
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
    onSelect,
    onPageChange,
    onPageSize,
  } = props
  if (!page) return <ProductTableSkeleton />
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
  return (
    <div className="space-y-6">
      <Table className="min-w-212 table-fixed">
        <ProductsTableHead />
        <TableBody>
          {page.items.map((item, i) => {
            const rowNumber =
              (page.page > 1
                ? (page.page - 1) * (page.page_size || page.items.length)
                : 0) +
              i +
              1
            const top = topGroupOf(item.main_group_name)
            return (
              <TableRow
                key={item.id}
                tabIndex={0}
                className="cursor-pointer"
                onClick={() => onSelect(item)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    onSelect(item)
                  }
                }}
              >
                <TableCell className="text-center text-sm text-muted-foreground">
                  <PersianNumber value={rowNumber} />
                </TableCell>
                <TableCell className="wrap-break-word whitespace-normal">
                  <span className="text-sm font-medium">{item.name}</span>
                </TableCell>
                <TableCell className="text-center text-sm text-muted-foreground">
                  <span
                    dir="ltr"
                    className="inline-block max-w-full truncate align-middle"
                  >
                    {item.sku}
                  </span>
                </TableCell>
                <TableCell className="text-center text-sm font-medium">
                  {top ?? <span className="text-muted-foreground">—</span>}
                </TableCell>
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
                <TableCell className="truncate text-center text-sm">
                  {item.unit_name ?? (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-center">
                  <Price value={item.price} />
                </TableCell>
                <TableCell className="text-center text-muted-foreground">
                  —
                </TableCell>
                <TableCell className="text-center text-muted-foreground">
                  —
                </TableCell>
                <TableCell className="text-center text-muted-foreground">
                  —
                </TableCell>
                <TableCell className="text-center">
                  <StockCell value={item.stock} threshold={threshold} />
                </TableCell>
              </TableRow>
            )
          })}
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
}

// Error state drawn inside the table itself, so it reads as "this table
// failed to load" instead of a detached card. Content is start-aligned on
// mobile: the table scrolls horizontally there and the start edge is the
// only part guaranteed to be on screen.
export function ProductsTableError({ message, onRetry }: TableErrorProps) {
  return (
    <Table className="min-w-212 table-fixed">
      <ProductsTableHead />
      <TableBody>
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={COLUMN_COUNT} className="whitespace-normal">
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
