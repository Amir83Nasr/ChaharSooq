import { Pin } from "lucide-react"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/primitives/select"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import {
  formatPersianNumber,
  parsePriceFilterInput,
} from "@workspace/ui/lib/number"
import { cn } from "@workspace/ui/lib/utils"
import { TomanGlyph } from "@workspace/ui/persian/toman-glyph"
import {
  DataTableToolbar,
  SearchInput,
} from "@/components/data/data-table-toolbar"
import type { ProductSort, TopGroup } from "@/lib/api"
import { COMPETITOR_MARKETS } from "@/lib/competitor-price"
import type { CompetitorMarketFilter, StockFilter } from "@/lib/products-store"
import { TOP_GROUPS, isTopGroup } from "@/lib/top-groups"

export const SORT_LABELS: Record<ProductSort, string> = {
  category: "تفکیک دسته‌بندی",
  alphabetical: "حروف الفبا",
  newest: "جدیدترین",
  cheapest: "ارزان‌ترین",
  most_expensive: "گران‌ترین",
}

export const STOCK_FILTER_LABELS: Record<StockFilter, string> = {
  all: "همه موجودی‌ها",
  in: "موجود",
  out: "ناموجود",
  low: "موجودی کم",
}

interface ToolbarProps {
  q: string
  topGroup: TopGroup | null
  sort: ProductSort
  stock: StockFilter
  /** Selected competitor store; `best` shows the cheapest available rival. */
  market: CompetitorMarketFilter
  /** Toggle: show only owner-pinned products. */
  pinned: boolean
  minPrice: string
  maxPrice: string
  hasFilters: boolean
  onQ: (v: string) => void
  onTopGroup: (v: TopGroup | null) => void
  onSort: (v: ProductSort) => void
  onStock: (v: StockFilter) => void
  onMarketChange: (v: CompetitorMarketFilter) => void
  onPinnedChange: (v: boolean) => void
  onMinPrice: (v: string) => void
  onMaxPrice: (v: string) => void
  onClear: () => void
}

export function ProductsToolbar(props: ToolbarProps) {
  const {
    q,
    topGroup,
    sort,
    stock,
    market,
    pinned,
    minPrice,
    maxPrice,
    hasFilters,
    onQ,
    onTopGroup,
    onSort,
    onStock,
    onMarketChange,
    onPinnedChange,
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
        className="max-md:h-11"
      />
      <Select
        value={topGroup === null ? "all" : topGroup}
        onValueChange={(v) =>
          onTopGroup(v === "all" || !isTopGroup(v) ? null : v)
        }
      >
        <SelectTrigger className="w-full sm:w-44" aria-label="فیلتر دسته‌بندی">
          <SelectValue>
            {(value: string | null) =>
              value === null || value === "all" ? "همه دسته‌بندی‌ها" : value
            }
          </SelectValue>
        </SelectTrigger>
        <SelectContent align="start">
          <SelectGroup>
            <SelectLabel>دسته‌بندی</SelectLabel>
            <SelectItem value="all">همه دسته‌بندی‌ها</SelectItem>
            {TOP_GROUPS.map((group) => (
              <SelectItem key={group} value={group}>
                {group}
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
            <SelectItem value="category">تفکیک دسته‌بندی</SelectItem>
            <SelectItem value="alphabetical">حروف الفبا</SelectItem>
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
            <SelectItem value="all">همه موجودی‌ها</SelectItem>
            <SelectItem value="in">موجود</SelectItem>
            <SelectItem value="out">ناموجود</SelectItem>
            <SelectItem value="low">موجودی کم</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <Select
        value={market}
        onValueChange={(v) => onMarketChange(v as CompetitorMarketFilter)}
      >
        <SelectTrigger className="w-full sm:w-44" aria-label="فروشگاه رقیب">
          <SelectValue>
            {(value: CompetitorMarketFilter | null) =>
              value
                ? (COMPETITOR_MARKETS.find((m) => m.store === value)?.label ??
                  "فروشگاه رقیب")
                : "فروشگاه رقیب"
            }
          </SelectValue>
        </SelectTrigger>
        <SelectContent align="start">
          <SelectGroup>
            <SelectLabel>قیمت رقبا</SelectLabel>
            {COMPETITOR_MARKETS.map((m) => (
              <SelectItem key={m.store} value={m.store}>
                {m.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        aria-pressed={pinned}
        aria-label={
          pinned ? "نمایش فقط پین\u200cشده‌ها" : "نمایش پین\u200cشده‌ها"
        }
        onClick={() => onPinnedChange(!pinned)}
        className={cn(
          pinned
            ? "border-primary/50 bg-primary/10 text-primary hover:bg-primary/15"
            : "text-muted-foreground"
        )}
      >
        <Pin className="size-4" aria-hidden="true" />
      </Button>
      <div className="relative w-full sm:w-40">
        <Input
          value={minPrice === "" ? "" : formatPersianNumber(minPrice)}
          onChange={(e) => onMinPrice(parsePriceFilterInput(e.target.value))}
          placeholder="کمینه قیمت"
          aria-label="کمینه قیمت (تومان)"
          inputMode="numeric"
          className="w-full pe-12 max-md:h-11"
        />
        {minPrice !== "" ? (
          <TomanGlyph className="inset-e-2.5 pointer-events-none absolute top-1/2 -translate-y-1/2 text-xs text-muted-foreground" />
        ) : null}
      </div>
      <div className="relative w-full sm:w-40">
        <Input
          value={maxPrice === "" ? "" : formatPersianNumber(maxPrice)}
          onChange={(e) => onMaxPrice(parsePriceFilterInput(e.target.value))}
          placeholder="بیشینه قیمت"
          aria-label="بیشینه قیمت (تومان)"
          inputMode="numeric"
          className="w-full pe-12 max-md:h-11"
        />
        {maxPrice !== "" ? (
          <TomanGlyph className="inset-e-2.5 pointer-events-none absolute top-1/2 -translate-y-1/2 text-xs text-muted-foreground" />
        ) : null}
      </div>
      {hasFilters ? (
        <Button
          variant="destructive"
          size="sm"
          onClick={onClear}
          className="max-md:h-11 max-md:w-full"
        >
          پاک‌سازی فیلترها
        </Button>
      ) : null}
    </DataTableToolbar>
  )
}
