"use client"

import { useEffect, useMemo, useState } from "react"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/primitives/select"
import { Badge } from "@workspace/ui/primitives/badge"
import { Button } from "@workspace/ui/primitives/button"
import { PersianDate } from "@workspace/ui/persian/persian-date"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"
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

type CardexView = "bar" | "line" | "table"

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

/** Purchase/sale history recorded in Parsina for the selected product. */
export function ProductCardexPanel({ productId }: { productId: number }) {
  const [period, setPeriod] = useState<CardexPeriodKey>("7_days")
  const [direction, setDirection] = useState<CardexDirection>("all")
  const [view, setView] = useState<CardexView>("bar")
  const [report, setReport] = useState<ProductCardex | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .productCardex(productId, period)
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
  }, [productId, period])

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

  return (
    <section className="space-y-3 text-start">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-medium text-muted-foreground">
          خرید و فروش ثبت‌شده در پارسینا
        </h3>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <Select
            value={period}
            onValueChange={(value) => setPeriod(value as CardexPeriodKey)}
          >
            <SelectTrigger
              className="w-full sm:w-40"
              aria-label="بازه کارتکس کالا"
            >
              <SelectValue>
                {(value: string | null) =>
                  periods.find((item) => item.key === value)?.label ??
                  "۷ روز گذشته"
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
            </SelectContent>
          </Select>
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

      {loading ? (
        <p className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
          در حال خواندن کارتکس…
        </p>
      ) : report?.configured === false ? (
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
