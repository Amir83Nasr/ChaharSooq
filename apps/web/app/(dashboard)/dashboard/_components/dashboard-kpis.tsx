import Link from "next/link"
import { Package, PackageX, Percent, TriangleAlert, Wallet } from "lucide-react"

import { Card, CardContent } from "@workspace/ui/primitives/card"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"
import { cn } from "@workspace/ui/lib/utils"

import type { DashboardOverview } from "@/lib/api"

type DashboardKpisProps = {
  overview: DashboardOverview
  threshold: number
}

const LINK_CARD_CLASS =
  "block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"

function KpiCard({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <Card
      className={cn(
        "h-full transition-[border-color,box-shadow] hover:border-foreground/25 hover:shadow-sm",
        className
      )}
    >
      <CardContent className="flex h-full flex-col gap-1.5 px-5 py-4">
        {children}
      </CardContent>
    </Card>
  )
}

function KpiLabel({
  icon,
  children,
}: {
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
      {icon}
      {children}
    </p>
  )
}

export function DashboardKpis({ overview, threshold }: DashboardKpisProps) {
  const coveragePercent =
    overview.appliance_total > 0
      ? Math.round(
          (overview.competitor_coverage / overview.appliance_total) * 100
        )
      : 0
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
      <div className="col-span-2">
        <KpiCard>
          <KpiLabel icon={<Wallet className="size-4" aria-hidden="true" />}>
            ارزش موجودی
          </KpiLabel>
          <Price value={overview.stock_value} className="text-2xl font-bold" />
          <p className="text-xs text-muted-foreground">مجموع قیمت × موجودی</p>
        </KpiCard>
      </div>

      <Link
        href="/products"
        className={LINK_CARD_CLASS}
        aria-label="مشاهده همه محصولات"
      >
        <KpiCard>
          <KpiLabel icon={<Package className="size-4" aria-hidden="true" />}>
            کل کالاها
          </KpiLabel>
          <p className="text-2xl font-bold">
            <PersianNumber value={overview.total} />
          </p>
          <p className="text-xs text-muted-foreground">قلم کالای فعال</p>
        </KpiCard>
      </Link>

      <Link
        href="/products?stock=low"
        className={LINK_CARD_CLASS}
        aria-label="مشاهده محصولات با موجودی کم"
      >
        <KpiCard>
          <KpiLabel
            icon={<TriangleAlert className="size-4" aria-hidden="true" />}
          >
            موجودی کم
          </KpiLabel>
          <p className="text-2xl font-bold">
            <PersianNumber value={overview.low} />
          </p>
          <p className="text-xs text-muted-foreground">
            آستانه: <PersianNumber value={threshold} /> قلم
          </p>
        </KpiCard>
      </Link>

      <Link
        href="/products?stock=out"
        className={LINK_CARD_CLASS}
        aria-label="مشاهده محصولات ناموجود"
      >
        <KpiCard>
          <KpiLabel icon={<PackageX className="size-4" aria-hidden="true" />}>
            ناموجود
          </KpiLabel>
          <p className="text-2xl font-bold">
            <PersianNumber value={overview.out} />
          </p>
          <p className="text-xs text-muted-foreground">موجودی صفر</p>
        </KpiCard>
      </Link>

      <KpiCard>
        <KpiLabel icon={<Percent className="size-4" aria-hidden="true" />}>
          پوشش قیمت رقیب
        </KpiLabel>
        <p className="text-2xl font-bold">
          <PersianNumber value={coveragePercent} />٪
        </p>
        <p className="text-xs text-muted-foreground">
          <PersianNumber value={overview.competitor_coverage} /> از{" "}
          <PersianNumber value={overview.appliance_total} /> قلم لوازم خانگی
        </p>
      </KpiCard>
    </div>
  )
}
