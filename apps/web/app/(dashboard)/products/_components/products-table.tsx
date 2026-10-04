import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { Badge } from "@workspace/ui/components/badge"
import { TablePagination } from "@workspace/ui/components/pagination"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { EmptyState } from "@workspace/ui/components/state"
import { Price } from "@workspace/ui/components/price"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { PackageSearch } from "lucide-react"
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

export function ProductTableSkeleton() {
  return (
    <div aria-label="در حال بارگذاری">
      <Table className="min-w-212 table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead>نام</TableHead>
            <TableHead className="text-center">کد</TableHead>
            <TableHead>دسته‌بندی</TableHead>
            <TableHead className="text-center">قیمت</TableHead>
            <TableHead className="text-center">موجودی</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: 5 }).map((_, i) => (
            <TableRow key={i}>
              {Array.from({ length: 5 }).map((_, j) => (
                <TableCell key={j} className={j > 0 ? "text-center" : ""}>
                  <Skeleton className={j > 0 ? "mx-auto h-4 w-20" : "h-4 w-20"} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function ProductsTable(props: TableProps) {
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
        title={hasFilters ? "محصولی با این فیلترها یافت نشد" : "محصولی ثبت نشده است"}
        hint={hasFilters ? "فیلترها را تغییر دهید یا پاک کنید." : "اولین محصول را از طریق API اضافه کنید."}
        icon={<PackageSearch className="size-10 text-muted-foreground" />}
      />
    )
  }
  return (
    <div className="space-y-6">
      <Table className="min-w-212 table-fixed">
        <colgroup>
          <col className="w-44" />
          <col className="w-36" />
          <col className="w-52" />
          <col className="w-28" />
          <col className="w-24" />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">نام</TableHead>
            <TableHead scope="col" className="text-center">کد</TableHead>
            <TableHead scope="col">دسته‌بندی</TableHead>
            <TableHead scope="col" className="text-center">قیمت</TableHead>
            <TableHead scope="col" className="text-center">موجودی</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((item) => (
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
              <TableCell className="whitespace-normal wrap-break-word">
                <span className="text-sm font-medium">{item.name}</span>
              </TableCell>
              <TableCell className="text-center text-sm text-muted-foreground">
                <span dir="ltr" className="inline-block max-w-full truncate align-middle">
                  {item.sku}
                </span>
              </TableCell>
              <TableCell className="truncate">
                {item.category ? (
                  <Badge variant="secondary">{item.category.name}</Badge>
                ) : (
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
          ))}
        </TableBody>
      </Table>
      <TablePagination page={pageNum} totalPages={totalPages} onPageChange={onPageChange}>
        {showPageSize ? (
          <Select value={String(pageSize)} onValueChange={(v) => onPageSize(Number(v))}>
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
              {PAGE_SIZE_OPTIONS.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  <PersianNumber value={n} /> محصول در صفحه
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}
      </TablePagination>
    </div>
  )
}
