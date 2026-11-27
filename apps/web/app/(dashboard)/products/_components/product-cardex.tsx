"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { CalendarDaysIcon } from "lucide-react"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/primitives/select"
import { Badge } from "@workspace/ui/primitives/badge"
import { Button } from "@workspace/ui/primitives/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@workspace/ui/primitives/popover"
import { Separator } from "@workspace/ui/primitives/separator"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { Spinner } from "@workspace/ui/primitives/spinner"
import { JalaliRangeCalendar } from "@workspace/ui/persian/persian-calendar"
import { PersianDate } from "@workspace/ui/persian/persian-date"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"
import {
  compareJalaliParts,
  formatJalaliParts,
  jalaliDaySpan,
  jalaliPartsToIsoDay,
  toJalaliParts,
  toJalaliPartsUtc,
  type JalaliParts,
} from "@workspace/ui/lib/jalali"
import { cn } from "@workspace/ui/lib/utils"

import {
  ApiRequestError,
  api,
  type CardexEntry,
  type CardexPeriod,
  type CardexPeriodKey,
  type ProductCardex,
} from "@/lib/api"
import {
  ProductCardexChart,
  type CardexDirection,
} from "./product-cardex-chart"

const FALLBACK_PERIODS: CardexPeriod[] = [
  { key: "today", label: "امروز", from_date: "", to_date: "" },
  { key: "3_days", label: "۳ روز گذشته", from_date: "", to_date: "" },
  { key: "7_days", label: "۷ روز گذشته", from_date: "", to_date: "" },
  { key: "30_days", label: "۳۰ روز گذشته", from_date: "", to_date: "" },
]

/** Mirrors the API cap for a manual cardex window. */
const MAX_CUSTOM_RANGE_DAYS = 90
const CUSTOM_RANGE_LIMIT_HINT = "بازه دلخواه حداکثر ۹۰ روز است."
const CUSTOM_RANGE_TOO_LONG = "بازه انتخابی بیش از ۹۰ روز است."

type CardexView = "bar" | "line" | "table"

type CustomRange = { from: string; to: string }

const DIRECTION_OPTIONS: { value: CardexDirection; label: string }[] = [
  { value: "all", label: "همه" },
  { value: "purchase", label: "خرید" },
  { value: "sale", label: "فروش" },
]

const VIEW_OPTIONS: { value: CardexView; label: string }[] = [
  { value: "bar", label: "نمودار میله‌ای" },
  { value: "line", label: "نمودار خطی" },
  { value: "table", label: "جدول" },
]

function cardexError(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "دریافت کارتکس کالا انجام نشد. دوباره تلاش کنید."
}

/** ISO machine day in, Jalali parts out without a time-zone shift. */
function isoDayToJalali(iso: string): JalaliParts {
  return toJalaliPartsUtc(new Date(`${iso}T00:00:00Z`))
}

function SummaryCard({
  label,
  value,
  unit,
  amount,
  tone,
}: {
  label: string
  value: number
  unit: string
  amount: number
  tone: "purchase" | "sale"
}) {
  return (
    <div
      className={cn(
        "min-w-0 rounded-2xl border px-3 py-2.5",
        tone === "sale"
          ? "border-primary/30 bg-primary/5"
          : "border-border/70 bg-muted/30"
      )}
    >
      <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-base font-bold">
          <PersianNumber value={value} />
        </span>
        <span className="text-[11px] text-muted-foreground">{unit}</span>
      </p>
      <div className="mt-1 text-xs">
        <Price value={amount} />
      </div>
    </div>
  )
}

function SegmentedFilter<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex h-11 w-full items-center rounded-2xl border border-border/70 bg-muted/40 p-0.5 sm:h-8 sm:w-auto"
    >
      {options.map((option) => {
        const active = option.value === value
        return (
          <Button
            key={option.value}
            type="button"
            variant="ghost"
            size="xs"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              "h-full flex-1 rounded-xl px-2.5 text-xs sm:flex-none",
              active
                ? "bg-background text-foreground shadow-xs hover:bg-background"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {option.label}
          </Button>
        )
      })}
    </div>
  )
}

/**
 * Reserves the exact shape of the loaded cardex (summary cards, hint, chart)
 * so the first paint already matches the final layout and nothing jumps when
 * the report arrives.
 */
function ProductCardexSkeleton() {
  return (
    <div role="status" aria-label="در حال خواندن کارتکس…" className="space-y-3">
      <span className="sr-only">در حال خواندن کارتکس…</span>
      <div className="grid grid-cols-2 gap-2" aria-hidden="true">
        {[0, 1].map((index) => (
          <div
            key={index}
            className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-2.5"
          >
            <Skeleton className="h-3 w-16" />
            <Skeleton className="mt-1.5 h-5 w-24" />
            <Skeleton className="mt-1.5 h-4 w-28" />
          </div>
        ))}
      </div>
      <Skeleton className="mx-1 h-3 w-64 max-w-full" aria-hidden="true" />
      <div
        className="rounded-2xl border border-border/70 bg-muted/20 p-3"
        aria-hidden="true"
      >
        <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1.5">
            <Skeleton className="h-3.5 w-40" />
            <Skeleton className="h-3 w-56 max-w-full" />
          </div>
          <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton className="h-52 w-full rounded-xl sm:h-60" />
      </div>
    </div>
  )
}

/** Purchase/sale history recorded in Parsina for the selected product. */
export function ProductCardexPanel({ productId }: { productId: number }) {
  const [period, setPeriod] = useState<CardexPeriodKey>("7_days")
  const [direction, setDirection] = useState<CardexDirection>("all")
  const [view, setView] = useState<CardexView>("bar")
  const [report, setReport] = useState<ProductCardex | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // The manual window is applied only after both ends are confirmed; until
  // then the previous report stays visible behind the picker.
  const [customRange, setCustomRange] = useState<CustomRange | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [draftFrom, setDraftFrom] = useState<JalaliParts | null>(null)
  const [draftTo, setDraftTo] = useState<JalaliParts | null>(null)
  const [rangeError, setRangeError] = useState<string | null>(null)
  const previousPeriod = useRef<CardexPeriodKey>("7_days")
  const pickerAnchor = useRef<HTMLDivElement | null>(null)

  const today = useMemo(() => toJalaliParts(new Date()), [])

  useEffect(() => {
    if (period === "custom" && customRange === null) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .productCardex(productId, period, customRange ?? undefined)
      .then((data) => {
        if (!cancelled) setReport(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(cardexError(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [productId, period, customRange])

  // Refetches keep the previous report on screen; only the first load for a
  // product uses the skeleton.
  const refreshing = loading && report !== null
  const periods = report?.periods?.length ? report.periods : FALLBACK_PERIODS
  const entries: CardexEntry[] = report?.entries ?? []
  const filteredEntries = useMemo(
    () =>
      direction === "all"
        ? entries
        : entries.filter((entry) => entry.kind === direction),
    [direction, entries]
  )
  const cancelledCount = filteredEntries.filter(
    (entry) => entry.is_cancelled
  ).length
  const activeFilteredCount = filteredEntries.length - cancelledCount
  const directionNoun = direction === "sale" ? "فروش" : "خرید"

  function periodLabel(value: CardexPeriodKey | null): string {
    if (value === "custom") {
      return customRange
        ? `${formatJalaliParts(isoDayToJalali(customRange.from))} تا ${formatJalaliParts(isoDayToJalali(customRange.to))}`
        : "بازه دلخواه"
    }
    return periods.find((item) => item.key === value)?.label ?? "۷ روز گذشته"
  }

  function openCustomPicker() {
    setRangeError(null)
    setPickerOpen(true)
    if (customRange !== null) {
      setDraftFrom(isoDayToJalali(customRange.from))
      setDraftTo(isoDayToJalali(customRange.to))
      return
    }
    if (report !== null) {
      setDraftFrom(isoDayToJalali(report.from_date))
      setDraftTo(isoDayToJalali(report.to_date))
      return
    }
    setDraftFrom(null)
    setDraftTo(null)
  }

  function handlePeriodChange(value: CardexPeriodKey) {
    if (value === "custom") {
      if (period !== "custom") previousPeriod.current = period
      setPeriod("custom")
      openCustomPicker()
      return
    }
    setPickerOpen(false)
    setPeriod(value)
  }

  function handlePickerOpenChange(open: boolean) {
    setPickerOpen(open)
    // Dismissing the picker without applying a range must not leave the tab
    // stuck on an empty "custom" window.
    if (!open && period === "custom" && customRange === null) {
      setPeriod(previousPeriod.current)
    }
  }

  function handleSelectDay(day: JalaliParts) {
    setRangeError(null)
    if (draftFrom === null || draftTo !== null) {
      setDraftFrom(day)
      setDraftTo(null)
      return
    }
    if (compareJalaliParts(day, draftFrom) < 0) {
      setDraftTo(draftFrom)
      setDraftFrom(day)
      return
    }
    setDraftTo(day)
  }

  function applyCustomRange() {
    if (draftFrom === null || draftTo === null) return
    if (jalaliDaySpan(draftFrom, draftTo) > MAX_CUSTOM_RANGE_DAYS) {
      setRangeError(CUSTOM_RANGE_TOO_LONG)
      return
    }
    setCustomRange({
      from: jalaliPartsToIsoDay(draftFrom),
      to: jalaliPartsToIsoDay(draftTo),
    })
    setPickerOpen(false)
  }

  return (
    <section className="space-y-3 text-start">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          خرید و فروش ثبت‌شده در پارسینا
          <Spinner active={refreshing} className="size-3.5" />
          {refreshing ? (
            <span className="sr-only">در حال به‌روزرسانی…</span>
          ) : null}
        </h3>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <div
            ref={pickerAnchor}
            className="flex w-full items-center gap-1 sm:w-auto"
          >
            <Popover open={pickerOpen} onOpenChange={handlePickerOpenChange}>
              <Select
                value={period}
                onValueChange={(value) =>
                  handlePeriodChange(value as CardexPeriodKey)
                }
              >
                <SelectTrigger
                  className="w-full sm:w-auto sm:min-w-40"
                  aria-label="بازه کارتکس کالا"
                >
                  <SelectValue>
                    {(value: string | null) =>
                      periodLabel(value as CardexPeriodKey | null)
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectGroup>
                    <SelectLabel>بازه گزارش</SelectLabel>
                    {periods.map((item) => (
                      <SelectItem key={item.key} value={item.key}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                  <SelectSeparator />
                  <SelectGroup>
                    <SelectItem value="custom">بازه دلخواه…</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
              {period === "custom" ? (
                <PopoverTrigger
                  render={
                    <Button
                      type="button"
                      variant="outline"
                      size="icon-sm"
                      aria-label="تغییر بازه دلخواه"
                      className="max-md:size-11"
                    />
                  }
                >
                  <CalendarDaysIcon />
                </PopoverTrigger>
              ) : null}
              <PopoverContent
                anchor={pickerAnchor}
                align="start"
                className="w-[19.5rem] p-3"
              >
                <JalaliRangeCalendar
                  from={draftFrom}
                  to={draftTo}
                  maxDate={today}
                  onSelect={handleSelectDay}
                />
                <Separator className="my-3" />
                <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                  <span>
                    از: {draftFrom ? formatJalaliParts(draftFrom) : "—"}
                  </span>
                  <span>تا: {draftTo ? formatJalaliParts(draftTo) : "—"}</span>
                </div>
                <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
                  {CUSTOM_RANGE_LIMIT_HINT}
                </p>
                {rangeError ? (
                  <p role="alert" className="mt-2 text-[11px] text-destructive">
                    {rangeError}
                  </p>
                ) : null}
                <div className="mt-3 flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    className="flex-1"
                    disabled={draftFrom === null || draftTo === null}
                    onClick={applyCustomRange}
                  >
                    اعمال بازه
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setPickerOpen(false)}
                  >
                    بستن
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          </div>
          <SegmentedFilter
            label="نوع تراکنش کارتکس"
            value={direction}
            options={DIRECTION_OPTIONS}
            onChange={setDirection}
          />
          <SegmentedFilter
            label="نحوه نمایش کارتکس"
            value={view}
            options={VIEW_OPTIONS}
            onChange={setView}
          />
        </div>
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-2xl border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
        >
          {error}
        </p>
      ) : null}

      {report === null ? (
        error === null ? (
          <ProductCardexSkeleton />
        ) : null
      ) : report.configured === false ? (
        <p className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
          اتصال پارسینا تنظیم نشده است.
        </p>
      ) : (
        <>
          <div
            className={cn(
              "grid gap-2",
              direction === "all" ? "grid-cols-2" : "grid-cols-1"
            )}
          >
            {direction !== "sale" ? (
              <SummaryCard
                label="میزان خرید"
                value={report?.summary.purchase_quantity ?? 0}
                unit="عدد"
                amount={report?.summary.purchase_amount ?? 0}
                tone="purchase"
              />
            ) : null}
            {direction !== "purchase" ? (
              <SummaryCard
                label="میزان فروش"
                value={report?.summary.sale_quantity ?? 0}
                unit="عدد"
                amount={report?.summary.sale_amount ?? 0}
                tone="sale"
              />
            ) : null}
          </div>

          {filteredEntries.length > 0 ? (
            <p className="px-1 text-[11px] leading-5 text-muted-foreground">
              {cancelledCount > 0
                ? view === "table"
                  ? `تعداد ${cancelledCount} فاکتور باطل فقط در جدول نمایش داده شده و در جمع بالا لحاظ نشده است.`
                  : `تعداد ${cancelledCount} فاکتور باطل در نمودار و جمع بالا لحاظ نشده است.`
                : "جمع بالا بر اساس فاکتورهای معتبر پارسینا محاسبه شده است."}
            </p>
          ) : null}

          {entries.length === 0 ? (
            <p className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
              برای کالا در این بازه خرید یا فروشی ثبت نشده است.
            </p>
          ) : filteredEntries.length === 0 ? (
            <p className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
              برای کالا در این بازه {directionNoun}ی ثبت نشده است.
            </p>
          ) : view !== "table" ? (
            report ? (
              activeFilteredCount > 0 ? (
                <ProductCardexChart
                  entries={filteredEntries}
                  report={report}
                  direction={direction}
                  variant={view}
                />
              ) : (
                <p className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
                  فاکتور معتبری برای نمایش نمودار وجود ندارد.
                </p>
              )
            ) : null
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-border/70">
              <table className="w-full min-w-[30rem] text-start text-xs">
                <thead className="bg-muted/40 text-muted-foreground">
                  <tr>
                    <th
                      scope="col"
                      className="px-3 py-2 text-start font-medium"
                    >
                      تاریخ
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-start font-medium"
                    >
                      نوع
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-start font-medium"
                    >
                      شماره فاکتور
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-start font-medium"
                    >
                      طرف مقابل
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-start font-medium"
                    >
                      تعداد
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-start font-medium"
                    >
                      مبلغ خالص
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEntries.map((entry) => (
                    <tr
                      key={`${entry.kind}-${entry.invoice_id}-${entry.invoice_date ?? ""}`}
                      className="border-t border-border/60"
                    >
                      <td className="px-3 py-2 whitespace-nowrap">
                        {entry.invoice_date ? (
                          <PersianDate value={entry.invoice_date} />
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className="flex flex-wrap items-center gap-1">
                          {entry.kind === "sale" ? "فروش" : "خرید"}
                          {entry.is_cancelled ? (
                            <Badge
                              variant="destructive"
                              className="px-1.5 py-0 text-[10px]"
                            >
                              باطل
                            </Badge>
                          ) : null}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        {entry.invoice_number !== null ? (
                          <PersianNumber value={entry.invoice_number} />
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2">{entry.counterparty ?? "—"}</td>
                      <td className="px-3 py-2">
                        <PersianNumber value={entry.quantity} />
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <Price value={entry.net_price} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
