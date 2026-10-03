import type { Metadata } from "next"

import { PersianDate } from "@workspace/ui/components/persian-date"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { PageHeader } from "@workspace/ui/components/page-header"
import { Price } from "@workspace/ui/components/price"

export const metadata: Metadata = { title: "داشبورد | چهارسوق" }

const KPIS = [
  { label: "فروش امروز", value: 1250000 },
  { label: "سفارش‌های امروز", value: 48, plain: true },
  { label: "موجودی کم", value: 7, plain: true },
] as const

export default function DashboardPage() {
  return (
    <>
      <PageHeader title="داشبورد" subtitle="نمای کلی فروشگاه" />
      <p className="text-sm text-muted-foreground">
        امروز: <PersianDate value={new Date()} />
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {KPIS.map((kpi) => (
          <div key={kpi.label} className="rounded-lg border border-border p-4">
            <p className="text-sm text-muted-foreground">{kpi.label}</p>
            <p className="mt-1 text-lg font-bold">
              {"plain" in kpi && kpi.plain ? (
                <PersianNumber value={kpi.value} />
              ) : (
                <Price value={kpi.value} />
              )}
            </p>
          </div>
        ))}
      </div>
    </>
  )
}
