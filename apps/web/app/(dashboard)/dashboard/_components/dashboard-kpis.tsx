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

export function DashboardKpis({ overview, threshold }: DashboardKpisProps) {
  const coveragePercent =
    overview.total > 0
      ? Math.round((overview.competitor_coverage / overview.total) * 100)
      : 0
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
      <Card>
        <CardContent className="flex flex-col gap-2 p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="rounded-lg bg-primary/10 p-2 text-primary">
              <Wallet className="size-4" />
            </span>
            <p className="text-sm">ارزش موجودی</p>
          </div>
          <Price value={overview.stock_value} className="text-2xl font-bold" />
          <p className="text-xs text-muted-foreground">مجموع قیمت × موجودی</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-2 p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="rounded-lg bg-muted p-2">
              <Package className="size-4" />
            </span>
            <p className="text-sm">کل کالاها</p>
          </div>
          <p className="text-2xl font-bold">
            <PersianNumber value={overview.total} />
          </p>
          <p className="text-xs text-muted-foreground">قلم کالای فعال</p>
        </CardContent>
      </Card>

      <Card className={cn(overview.low > 0 && "border-amber-500/30")}>
        <CardContent className="flex flex-col gap-2 p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="rounded-lg bg-amber-500/10 p-2 text-amber-600 dark:text-amber-500">
              <TriangleAlert className="size-4" />
            </span>
            <p className="text-sm">موجودی کم</p>
          </div>
          <p className="text-2xl font-bold">
            <PersianNumber value={overview.low} />
          </p>
          <p className="text-xs text-muted-foreground">
            آستانه: <PersianNumber value={threshold} /> قلم
          </p>
        </CardContent>
      </Card>

      <Card className={cn(overview.out > 0 && "border-rose-500/30")}>
        <CardContent className="flex flex-col gap-2 p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="rounded-lg bg-rose-500/10 p-2 text-rose-600 dark:text-rose-500">
              <PackageX className="size-4" />
            </span>
            <p className="text-sm">ناموجود</p>
          </div>
          <p className="text-2xl font-bold">
            <PersianNumber value={overview.out} />
          </p>
          <p className="text-xs text-muted-foreground">موجودی صفر</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-2 p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="rounded-lg bg-sky-500/10 p-2 text-sky-600 dark:text-sky-500">
              <Percent className="size-4" />
            </span>
            <p className="text-sm">پوشش قیمت رقیب</p>
          </div>
          <p className="text-2xl font-bold">
            <PersianNumber value={coveragePercent} />٪
          </p>
          <p className="text-xs text-muted-foreground">
            <PersianNumber value={overview.competitor_coverage} /> از{" "}
            <PersianNumber value={overview.total} /> قلم
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
