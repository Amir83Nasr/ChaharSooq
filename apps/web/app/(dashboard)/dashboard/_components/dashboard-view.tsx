"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"

import { PageHeader } from "@workspace/ui/layout/page-header"
import { EmptyState, ErrorState } from "@workspace/ui/feedback/state"
import { Button, buttonVariants } from "@workspace/ui/primitives/button"
import { Card, CardContent } from "@workspace/ui/primitives/card"
import { Skeleton } from "@workspace/ui/primitives/skeleton"

import {
  api,
  ApiRequestError,
  GENERIC_ERROR_MESSAGE,
  type CatalogSection,
  type CompetitorSyncStatus,
  type DashboardOverview,
  type SyncStatus,
} from "@/lib/api"
import { leaveToLogin } from "@/lib/auth-navigation"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import { CatalogBreakdown } from "./dashboard-catalog"
import { DashboardKpis } from "./dashboard-kpis"
import { SyncStatusCards } from "./dashboard-sync-cards"

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-4 w-56" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        {Array.from({ length: 5 }, (_, i) => (
          <Card key={i} className={i === 0 ? "col-span-2" : undefined}>
            <CardContent className="flex flex-col gap-2 p-5">
              <Skeleton className="h-8 w-24" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-4 w-28" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Skeleton className="h-96" />
    </div>
  )
}

export function DashboardView() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [breakdown, setBreakdown] = useState<CatalogSection[] | null>(null)
  const [parsina, setParsina] = useState<SyncStatus | null>(null)
  const [competitor, setCompetitor] = useState<CompetitorSyncStatus | null>(
    null
  )
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const goLogin = useCallback(() => {
    leaveToLogin()
  }, [])

  useEffect(() => {
    let cancelled = false
    setError(null)
    const fail = (err: unknown) => {
      if (cancelled) return
      if (err instanceof ApiRequestError && err.status === 401) {
        goLogin()
        return
      }
      setError(
        err instanceof ApiRequestError ? err.message : GENERIC_ERROR_MESSAGE
      )
    }
    api
      .settings()
      .catch(() => null)
      .then(async (settings) => {
        const next =
          settings && Number.isFinite(settings.low_stock_threshold)
            ? Math.max(0, Math.floor(settings.low_stock_threshold))
            : DEFAULT_LOW_STOCK_THRESHOLD
        if (!cancelled) setThreshold(next)
        // One aggregated fetch (overview + catalog) plus the two sync
        // statuses in parallel — the summary short-circuits gaps/catalog
        // work when the catalog is empty.
        const [summary, parsinaData, competitorData] = await Promise.all([
          api.dashboardSummary(next),
          api.parsinaStatus().catch(() => null),
          api.competitorStatus().catch(() => null),
        ])
        if (cancelled) return
        setOverview(summary.overview)
        // Sync health degrades gracefully — a failed status read hides
        // that source instead of failing the whole dashboard.
        setBreakdown(summary.overview.total > 0 ? summary.catalog : null)
        setParsina(parsinaData)
        setCompetitor(competitorData)
      })
      .catch(fail)
    return () => {
      cancelled = true
    }
  }, [goLogin, reloadKey])

  return (
    <>
      <PageHeader title="داشبورد" subtitle="نمای لحظه‌ای موجودی فروشگاه" />
      {error ? (
        <ErrorState
          title="خطا در بارگذاری داشبورد"
          hint={error}
          action={
            <Button
              onClick={() => setReloadKey((v) => v + 1)}
              className="h-11 md:h-8"
            >
              تلاش مجدد
            </Button>
          }
        />
      ) : overview === null ? (
        <DashboardSkeleton />
      ) : overview.total === 0 ? (
        <EmptyState
          title="کالایی ثبت نشده است"
          hint="پس از همگام‌سازی با پارسبنا، آمار موجودی در این بخش نمایش داده می‌شود."
          action={
            <Link
              href="/products"
              className={buttonVariants({
                variant: "outline",
                className: "h-11 md:h-8",
              })}
            >
              مشاهده محصولات
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <SyncStatusCards parsina={parsina} competitor={competitor} />
          <DashboardKpis overview={overview} threshold={threshold} />
          {breakdown && breakdown.some((s) => s.items > 0) ? (
            <CatalogBreakdown sections={breakdown} />
          ) : null}
        </div>
      )}
    </>
  )
}
