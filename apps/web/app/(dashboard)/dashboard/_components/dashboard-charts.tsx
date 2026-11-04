import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"

import type { DashboardOverview } from "@/lib/api"

const DONUT_SIZE = 160
const DONUT_STROKE = 18
const DONUT_RADIUS = (DONUT_SIZE - DONUT_STROKE) / 2
const DONUT_CIRCUMFERENCE = 2 * Math.PI * DONUT_RADIUS

type Segment = {
  key: "in_stock" | "low" | "out"
  label: string
  value: number
  strokeClass: string
  dotClass: string
}

function segmentsOf(overview: DashboardOverview): Segment[] {
  return [
    {
      key: "in_stock",
      label: "موجود",
      value: overview.in_stock,
      strokeClass: "text-emerald-500",
      dotClass: "bg-emerald-500",
    },
    {
      key: "low",
      label: "موجودی کم",
      value: overview.low,
      strokeClass: "text-amber-500",
      dotClass: "bg-amber-500",
    },
    {
      key: "out",
      label: "ناموجود",
      value: overview.out,
      strokeClass: "text-rose-500",
      dotClass: "bg-rose-500",
    },
  ]
}

export function InventoryDonut({ overview }: { overview: DashboardOverview }) {
  const segments = segmentsOf(overview)
  let offset = 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>توزیع موجودی</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-6">
        <div
          className="relative"
          role="img"
          aria-label={`توزیع موجودی: ${overview.in_stock} موجود، ${overview.low} موجودی کم، ${overview.out} ناموجود`}
        >
          <svg
            width={DONUT_SIZE}
            height={DONUT_SIZE}
            viewBox={`0 0 ${DONUT_SIZE} ${DONUT_SIZE}`}
            className="-rotate-90"
          >
            <circle
              cx={DONUT_SIZE / 2}
              cy={DONUT_SIZE / 2}
              r={DONUT_RADIUS}
              fill="none"
              strokeWidth={DONUT_STROKE}
              stroke="currentColor"
              className="text-muted"
            />
            {overview.total > 0
              ? segments.map((segment) => {
                  if (segment.value <= 0) return null
                  const length =
                    (segment.value / overview.total) * DONUT_CIRCUMFERENCE
                  const dashOffset = -offset
                  offset += length
                  return (
                    <circle
                      key={segment.key}
                      cx={DONUT_SIZE / 2}
                      cy={DONUT_SIZE / 2}
                      r={DONUT_RADIUS}
                      fill="none"
                      strokeWidth={DONUT_STROKE}
                      stroke="currentColor"
                      strokeDasharray={`${length} ${DONUT_CIRCUMFERENCE - length}`}
                      strokeDashoffset={dashOffset}
                      strokeLinecap="butt"
                      className={segment.strokeClass}
                    />
                  )
                })
              : null}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
            <p className="text-2xl font-bold">
              <PersianNumber value={overview.total} />
            </p>
            <p className="text-xs text-muted-foreground">کل کالاها</p>
          </div>
        </div>
        <ul className="flex w-full flex-col gap-2.5">
          {segments.map((segment) => (
            <li key={segment.key} className="flex items-center gap-2 text-sm">
              <span
                aria-hidden="true"
                className={`size-2.5 shrink-0 rounded-full ${segment.dotClass}`}
              />
              <span className="text-muted-foreground">{segment.label}</span>
              <span className="ms-auto font-semibold">
                <PersianNumber value={segment.value} />
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

export function GroupBars({ overview }: { overview: DashboardOverview }) {
  const max = overview.groups[0]?.stock_value ?? 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>ارزش موجودی به تفکیک گروه</CardTitle>
      </CardHeader>
      <CardContent>
        {overview.groups.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            گروهی برای نمایش وجود ندارد.
          </p>
        ) : (
          <ul className="flex flex-col gap-5">
            {overview.groups.map((group) => (
              <li key={group.name}>
                <div className="flex items-baseline justify-between gap-2">
                  <p className="min-w-0 truncate text-sm font-medium">
                    {group.name}
                  </p>
                  <div className="flex shrink-0 items-baseline gap-2">
                    <span className="text-xs text-muted-foreground">
                      <PersianNumber value={group.count} /> قلم
                    </span>
                    <Price
                      value={group.stock_value}
                      className="text-sm font-semibold"
                    />
                  </div>
                </div>
                <div
                  className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted"
                  role="img"
                  aria-label={`${group.name}: ${group.count} قلم`}
                >
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{
                      width: `${max > 0 ? Math.max(4, Math.round((group.stock_value / max) * 100)) : 0}%`,
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
