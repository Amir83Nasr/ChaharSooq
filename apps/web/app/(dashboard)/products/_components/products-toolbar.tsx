import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import {
  formatPersianNumber,
  parsePriceFilterInput,
} from "@workspace/ui/lib/number"
import {
  DataTableToolbar,
  SearchInput,
} from "@/components/data-table-toolbar"
import type { CategoryOut, ProductSort } from "@/lib/api"

export type StockFilter = "all" | "in" | "out" | "low"

export const SORT_LABELS: Record<ProductSort, string> = {
  newest: "جدیدترین",
  cheapest: "ارزان‌ترین",
  most_expensive: "گران‌ترین",
}

export const STOCK_FILTER_LABELS: Record<StockFilter, string> = {
  all: "همه",
  in: "موجود",
  out: "ناموجود",
  low: "کم",
}

interface ToolbarProps {
  q: string
  categoryId: number | null
  categories: CategoryOut[]
  sort: ProductSort
  stock: StockFilter
  minPrice: string
  maxPrice: string
  hasFilters: boolean
  onQ: (v: string) => void
  onCategory: (v: number | null) => void
  onSort: (v: ProductSort) => void
  onStock: (v: StockFilter) => void
  onMinPrice: (v: string) => void
  onMaxPrice: (v: string) => void
  onClear: () => void
}

export function ProductsToolbar(props: ToolbarProps) {
  const {
    q,
    categoryId,
    categories,
    sort,
    stock,
    minPrice,
    maxPrice,
    hasFilters,
    onQ,
    onCategory,
    onSort,
    onStock,
    onMinPrice,
    onMaxPrice,
    onClear,
  } = props
  return (
    <DataTableToolbar>
      <SearchInput
        value={q}
        onChange={onQ}
        placeholder="جست‌وجو در نام یا کد…"
        aria-label="جست‌وجو در محصولات"
      />
      <Select
        value={categoryId === null ? "all" : String(categoryId)}
        onValueChange={(v) => onCategory(v === "all" ? null : Number(v))}
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
      <Select value={sort} onValueChange={(v) => onSort(v as ProductSort)}>
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
      <Select value={stock} onValueChange={(v) => onStock(v as StockFilter)}>
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
            <SelectItem value="low">کم</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <div className="relative w-full sm:w-40">
        <Input
          value={minPrice === "" ? "" : formatPersianNumber(minPrice)}
          onChange={(e) => onMinPrice(parsePriceFilterInput(e.target.value))}
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
          onChange={(e) => onMaxPrice(parsePriceFilterInput(e.target.value))}
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
        <Button variant="destructive" size="sm" onClick={onClear}>
          پاک‌سازی فیلترها
        </Button>
      ) : null}
    </DataTableToolbar>
  )
}
