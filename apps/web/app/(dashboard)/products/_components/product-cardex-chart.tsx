"use client"

import { useMemo } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  XAxis,
  YAxis,
} from "recharts"

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@workspace/ui/primitives/chart"
import { formatPersianDate } from "@workspace/ui/lib/date"
import { formatPersianNumber } from "@workspace/ui/lib/number"

import type { CardexEntry, ProductCardex } from "@/lib/api"

export type CardexDirection = "all" | "sale" | "purchase"

const chartConfig = {
  sale: {
    label: "فروش",
    color: "var(--chart-1)",
  },
  purchase: {
    label: "خرید",
    color: "var(--chart-2)",
  },
} satisfies ChartConfig

export type CardexChartVariant = "bar" | "line"

const DIRECTION_TITLE: Record<CardexDirection, string> = {
  all: "خرید و فروش",
  sale: "فروش",
  purchase: "خرید",
}

const VARIANT_TITLE: Record<CardexChartVariant, string> = {
  bar: "نمودار میله‌ای",
  line: "نمودار خطی",
}

type CardexChartPoint = {
  label: string
  sale: number
  purchase: number
}

const DAY_MS = 24 * 60 * 60 * 1000

function parseIsoDay(value: string): Date {
  // Noon UTC keeps the Jalali calendar day stable across display time zones.
  return new Date(`${value.slice(0, 10)}T12:00:00Z`)
}

function toIsoDay(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function formatQuantity(value: unknown): string {
  const numeric = typeof value === "number" ? value : Number(value)
  return Number.isFinite(numeric) && numeric > 0
    ? formatPersianNumber(numeric)
    : ""
}

function buildChartPoints(
  entries: CardexEntry[],
  report: ProductCardex
): CardexChartPoint[] {
  const window = report.periods.find((item) => item.key === report.period)
  if (!window) return []

  const totals = new Map<string, { sale: number; purchase: number }>()
  for (const entry of entries) {
    if (entry.is_cancelled || !entry.invoice_date) continue
    const date = entry.invoice_date.slice(0, 10)
    const current = totals.get(date) ?? { sale: 0, purchase: 0 }
    current[entry.kind] += entry.quantity
    totals.set(date, current)
  }

  const start = parseIsoDay(window.from_date).getTime()
  const end = parseIsoDay(window.to_date).getTime()
  const points: CardexChartPoint[] = []
  for (let time = start; time <= end; time += DAY_MS) {
    const date = toIsoDay(new Date(time))
    const total = totals.get(date) ?? { sale: 0, purchase: 0 }
    points.push({
      label: formatPersianDate(new Date(time)),
      sale: total.sale,
      purchase: total.purchase,
    })
  }
  return points
}

/** Daily purchase/sale quantities for the selected cardex window. */
export function ProductCardexChart({
  entries,
  report,
  direction = "all",
  variant = "bar",
}: {
  entries: CardexEntry[]
  report: ProductCardex
  direction?: CardexDirection
  variant?: CardexChartVariant
}) {
  const points = useMemo(
    () => buildChartPoints(entries, report),
    [entries, report]
  )
  const hasData = entries.some((entry) => !entry.is_cancelled)
  const showLabels = points.length <= 10
  const visibleKinds: ("sale" | "purchase")[] =
    direction === "all" ? ["sale", "purchase"] : [direction]

  if (!hasData || points.length === 0) return null

  const tooltipContent = (
    <ChartTooltipContent
      formatter={(value, name) => {
        const numeric = typeof value === "number" ? value : Number(value)
        const key = name === "sale" ? "sale" : "purchase"
        return (
          <div className="flex w-full items-center gap-2">
            <span
              aria-hidden="true"
              className="size-2 shrink-0 rounded-[2px]"
              style={{ backgroundColor: chartConfig[key].color }}
            />
            <span className="text-muted-foreground">
              {chartConfig[key].label}
            </span>
            <span className="ms-auto font-medium tabular-nums">
              {Number.isFinite(numeric) ? formatPersianNumber(numeric) : "—"}{" "}
              عدد
            </span>
          </div>
        )
      }}
    />
  )

  return (
    <div className="rounded-2xl border border-border/70 bg-muted/20 p-3">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium">
            {VARIANT_TITLE[variant]} {DIRECTION_TITLE[direction]}
          </p>
          <p className="mt-0.5 text-[11px] leading-4 text-muted-foreground">
            مقدار روزانه در بازه انتخابی، بر حسب عدد
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          {visibleKinds.map((key) => (
            <span key={key} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="size-2 rounded-[2px]"
                style={{ backgroundColor: chartConfig[key].color }}
              />
              {chartConfig[key].label}
            </span>
          ))}
        </div>
      </div>
      {/* The time axis always runs left → right; dir="rtl" only keeps the
          Persian tooltip text right-to-left. */}
      <ChartContainer
        config={chartConfig}
        dir="rtl"
        className="aspect-auto h-52 w-full sm:h-60"
      >
        {variant === "line" ? (
          <AreaChart
            accessibilityLayer
            data={points}
            margin={{ top: 24, right: 8, left: 8, bottom: 0 }}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              fontSize={10}
              interval="preserveStartEnd"
              minTickGap={8}
            />
            <YAxis hide />
            <ChartTooltip cursor={false} content={tooltipContent} />
            {visibleKinds.map((key) => (
              <Area
                key={key}
                dataKey={key}
                type="linear"
                fill={`var(--color-${key})`}
                fillOpacity={0.3}
                stroke={`var(--color-${key})`}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        ) : (
          <BarChart
            accessibilityLayer
            data={points}
            margin={{ top: 24, right: 8, left: 8, bottom: 0 }}
            barCategoryGap="26%"
            barGap={2}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              fontSize={10}
              interval="preserveStartEnd"
              minTickGap={8}
            />
            <YAxis hide />
            <ChartTooltip cursor={false} content={tooltipContent} />
            {direction !== "sale" ? (
              <Bar
                dataKey="purchase"
                fill="var(--color-purchase)"
                radius={[6, 6, 0, 0]}
              >
                {showLabels ? (
                  <LabelList
                    dataKey="purchase"
                    position="top"
                    offset={6}
                    fontSize={10}
                    className="fill-muted-foreground"
                    formatter={formatQuantity}
                  />
                ) : null}
              </Bar>
            ) : null}
            {direction !== "purchase" ? (
              <Bar
                dataKey="sale"
                fill="var(--color-sale)"
                radius={[6, 6, 0, 0]}
              >
                {showLabels ? (
                  <LabelList
                    dataKey="sale"
                    position="top"
                    offset={6}
                    fontSize={10}
                    className="fill-muted-foreground"
                    formatter={formatQuantity}
                  />
                ) : null}
              </Bar>
            ) : null}
          </BarChart>
        )}
      </ChartContainer>
    </div>
  )
}
