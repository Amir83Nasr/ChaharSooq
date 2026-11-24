"use client"

import { memo } from "react"
import { ChevronLeft } from "lucide-react"

import { Price } from "@workspace/ui/persian/price"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { formatPersianNumber } from "@workspace/ui/lib/number"
import { cn } from "@workspace/ui/lib/utils"
import { Button } from "@workspace/ui/primitives/button"
import { EmptyState } from "@workspace/ui/feedback/state"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { PackageSearch } from "lucide-react"
import { StockCell } from "@/components/data/products-stock-cell"
import {
  competitorForRow,
  showsCompetitorPrice,
  STORE_MARKET_LABELS,
  type CompetitorMarket,
} from "@/lib/competitor-price"
import { toTomanAmount } from "@/lib/money"
import type { ProductOut, ProductSort } from "@/lib/api"
import { initialRowWindow, useWindowedRows } from "./use-windowed-rows"

// Mobile cards are taller than table rows; a small first window keeps the
// initial commit cheap while the real heights are measured.
const CARD_EST_HEIGHT = 168
const CARD_INITIAL_ROWS = 8

function diffPercent(ours: number, theirs: number | null): number | null {
  if (theirs === null || theirs <= 0 || ours <= 0) return null
  return ((ours - theirs) / theirs) * 100
}

export function ProductMobileCard({
  item,
  market,
  threshold,
  onSelect,
}: {
  item: ProductOut
  market: CompetitorMarket
  threshold: number
  onSelect: (item: ProductOut) => void
}) {
  const top = item.top_group
  // The pricing formula comes from the product, not its catalog section.
  const exact = item.pricing_mode === "exact_competitor"
  const noCompetitor = item.pricing_mode === "no_competitor_price"
  const showCompetitor = showsCompetitorPrice(market, top)
  const competitor = showCompetitor
    ? competitorForRow(item.competitor_prices, market, top)
    : null
  const marketLabel =
    market === "best" && competitor
      ? STORE_MARKET_LABELS[competitor.store]
      : STORE_MARKET_LABELS[market]
  const amount = toTomanAmount(
    competitor?.price ?? null,
    competitor?.currency ?? null
  )
  const pct =
    !noCompetitor && exact && competitor?.is_fresh === true
      ? diffPercent(item.price, amount)
      : null

  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      aria-label={`مشاهده جزئیات ${item.name}`}
      className="flex min-h-11 w-full items-start gap-3 rounded-2xl border border-border bg-card p-3 text-start shadow-none transition-[border-color,box-shadow] active:scale-[0.995] active:border-foreground/25 sm:p-4"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-1.5">
        <span className="flex items-start justify-between gap-2">
          <span className="line-clamp-2 min-w-0 flex-1 text-sm leading-6 font-semibold wrap-break-word">
            {item.name}
          </span>
          <ChevronLeft
            className="mt-1 size-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
        </span>
        {/* Single quiet meta line: category context + SKU only. Row number
              is a list artifact and the brand repeats the product name, so
              both are dropped on mobile to keep the card scannable. */}
        {top || item.sku ? (
          <span className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
            {top ? <span className="shrink-0">{top}</span> : null}
            {top && item.sku ? (
              <span aria-hidden="true" className="shrink-0">
                ·
              </span>
            ) : null}
            {item.sku ? (
              <span dir="ltr" className="min-w-0 flex-1 truncate text-right">
                {item.sku}
              </span>
            ) : null}
          </span>
        ) : null}
        <span className="flex flex-wrap items-end justify-between gap-x-3 gap-y-1.5 pt-0.5">
          <span className="flex flex-col gap-0.5">
            <span className="text-[11px] text-muted-foreground">قیمت ما</span>
            <Price value={item.price} className="text-base font-bold" />
          </span>
          {showCompetitor || noCompetitor ? (
            <span className="flex flex-col items-end gap-0.5">
              <span className="text-[11px] text-muted-foreground">
                {marketLabel}
              </span>
              {noCompetitor ? (
                <span className="text-sm text-muted-foreground">—</span>
              ) : competitor?.price !== null &&
                competitor?.price !== undefined &&
                amount !== null &&
                amount !== undefined ? (
                <Price
                  value={amount}
                  className="text-sm font-semibold text-muted-foreground"
                />
              ) : (
                <span className="text-xs text-muted-foreground">
                  لینک ثبت نشده
                </span>
              )}
            </span>
          ) : null}
        </span>
        <span className="flex flex-wrap items-center justify-between gap-2 pt-0.5">
          <StockCell value={item.stock} threshold={threshold} />
          {pct !== null && !Object.is(Math.round(pct * 10) / 10, 0) ? (
            <span
              className={cn(
                "text-xs font-medium",
                pct > 0 ? "text-destructive" : "text-success"
              )}
            >
              {formatDiffCompact(pct)} {pct > 0 ? "گران‌تر" : "ارزان‌تر"}
            </span>
          ) : !noCompetitor &&
            !exact &&
            competitor?.price_change_percent != null ? (
            <span
              className={cn(
                "text-xs font-medium",
                competitor.price_change_percent > 0
                  ? "text-destructive"
                  : competitor.price_change_percent < 0
                    ? "text-success"
                    : "text-muted-foreground"
              )}
            >
              تغییر روزانه {formatDiffCompact(competitor.price_change_percent)}
            </span>
          ) : null}
        </span>
      </span>
    </button>
  )
}

function formatDiffCompact(diff: number): string {
  const rounded = Math.round(diff * 10) / 10
  const clean = Object.is(rounded, -0) ? 0 : rounded
  const absStr = Math.abs(clean).toFixed(1).replace(/\.0$/, "")
  return `${formatPersianNumber(absStr)}٪`
}

type CardEntry = { key: number; item: ProductOut }

function buildCardEntries(items: ProductOut[]): CardEntry[] {
  return items.map((item) => ({ key: item.id, item }))
}

export const ProductsCards = memo(function ProductsCards({
  items,
  sort: _sort,
  market,
  threshold,
  onSelect,
}: {
  items: ProductOut[]
  sort: ProductSort
  market: CompetitorMarket
  threshold: number
  onSelect: (item: ProductOut) => void
}) {
  // "Show all" can return the whole catalog; render only the viewport slice.
  // Spacing lives on each <li> so measured heights include the gap.
  const entries = buildCardEntries(items)
  const options = {
    estimatedRowHeight: CARD_EST_HEIGHT,
    initialRows: CARD_INITIAL_ROWS,
  }
  const { bodyRef, observeRow, win } = useWindowedRows<HTMLUListElement>(
    entries.length,
    (i) => entries[i]?.key ?? i,
    options
  )
  const count = entries.length
  const renderWin =
    win.end > count || (win.end === 0 && count > 0)
      ? initialRowWindow(count, options)
      : win

  return (
    <ul ref={bodyRef} className="flex flex-col">
      {renderWin.topPad > 0 ? (
        <li aria-hidden="true" style={{ height: renderWin.topPad }} />
      ) : null}
      {entries.slice(renderWin.start, renderWin.end).map((entry, k) => {
        const i = renderWin.start + k
        return (
          <li
            key={entry.key}
            ref={observeRow(i)}
            data-vi={i}
            className="pb-2.5"
          >
            <ProductMobileCard
              item={entry.item}
              market={market}
              threshold={threshold}
              onSelect={onSelect}
            />
          </li>
        )
      })}
      {renderWin.bottomPad > 0 ? (
        <li aria-hidden="true" style={{ height: renderWin.bottomPad }} />
      ) : null}
    </ul>
  )
})

export function ProductsMobileSkeleton() {
  return (
    <ul aria-label="در حال بارگذاری محصولات" className="flex flex-col gap-2.5">
      {Array.from({ length: 6 }).map((_, i) => (
        <li
          key={i}
          className="flex flex-col gap-1.5 rounded-2xl border border-border bg-card p-3"
        >
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-1/3" />
          <div className="flex items-end justify-between pt-0.5">
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-6 w-20" />
          </div>
          <div className="flex items-center justify-between pt-0.5">
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-4 w-20" />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function ProductsMobileEmpty({ hasFilters }: { hasFilters: boolean }) {
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

export function ProductsMobilePagination({
  pageNum,
  totalPages,
  onPageChange,
}: {
  pageNum: number
  totalPages: number
  onPageChange: (p: number) => void
}) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between gap-2 rounded-2xl border border-border bg-card px-3 py-2">
      <Button
        variant="ghost"
        disabled={pageNum <= 1}
        onClick={() => onPageChange(pageNum - 1)}
        aria-label="صفحه قبلی"
        className="h-11 flex-1 rounded-2xl"
      >
        قبلی
      </Button>
      <p className="shrink-0 text-sm text-muted-foreground">
        صفحه <PersianNumber value={pageNum} /> از{" "}
        <PersianNumber value={totalPages} />
      </p>
      <Button
        variant="ghost"
        disabled={pageNum >= totalPages}
        onClick={() => onPageChange(pageNum + 1)}
        aria-label="صفحه بعدی"
        className="h-11 flex-1 rounded-2xl"
      >
        بعدی
      </Button>
    </div>
  )
}
