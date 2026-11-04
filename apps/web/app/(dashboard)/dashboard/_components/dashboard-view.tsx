"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
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
  type Attention,
  type CompetitorGap,
  type CompetitorSyncStatus,
  type DashboardOverview,
  type SyncStatus,
} from "@/lib/api"
import { DEFAULT_LOW_STOCK_THRESHOLD } from "@/lib/inventory"
import { AttentionCard } from "./dashboard-attention"
import { CompetitorGaps } from "./dashboard-gaps"
import { DashboardKpis } from "./dashboard-kpis"
import { GroupBars, InventoryDonut } from "./dashboard-charts"
import { SyncStrip } from "./dashboard-sync-strip"

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-4 w-56" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Card key={i}>
            <CardContent className="flex flex-col gap-2 p-5">
              <Skeleton className="h-8 w-24" />
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-4 w-28" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-5">
        <Skeleton className="h-80 lg:col-span-2" />
        <Skeleton className="h-80 lg:col-span-3" />
      </div>
      <div className="grid gap-4 lg:grid-cols-5">
        <Skeleton className="h-80 lg:col-span-3" />
        <Skeleton className="h-80 lg:col-span-2" />
      </div>
    </div>
  )
}

export function DashboardView() {
  const router = useRouter()
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [gaps, setGaps] = useState<CompetitorGap[]>([])
  const [attention, setAttention] = useState<Attention | null>(null)
  const [parsina, setParsina] = useState<SyncStatus | null>(null)
  const [competitor, setCompetitor] = useState<CompetitorSyncStatus | null>(
    null
  )
  const [threshold, setThreshold] = useState(DEFAULT_LOW_STOCK_THRESHOLD)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const goLogin = useCallback(() => {
    router.replace("/login")
    router.refresh()
  }, [router])

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
        const data = await api.dashboardOverview(next)
        if (cancelled) return
        setOverview(data)
        // Sync health degrades gracefully — a failed status read hides
        // that source instead of failing the whole dashboard.
        const [gapsData, attentionData, parsinaData, competitorData] =
          data.total > 0
            ? await Promise.all([
                api.dashboardGaps(),
                api.dashboardAttention(next),
                api.parsinaStatus().catch(() => null),
                api.competitorStatus().catch(() => null),
              ])
            : [[], null, null, null]
        if (cancelled) return
        setGaps(gapsData)
        setAttention(attentionData)
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
            <Button onClick={() => setReloadKey((v) => v + 1)}>
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
              className={buttonVariants({ variant: "outline" })}
            >
              مشاهده محصولات
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <SyncStrip parsina={parsina} competitor={competitor} />
          <DashboardKpis overview={overview} threshold={threshold} />
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <InventoryDonut overview={overview} />
            </div>
            <div className="lg:col-span-3">
              <CompetitorGaps gaps={gaps} />
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <GroupBars overview={overview} />
            </div>
            <div className="lg:col-span-2">
              {attention ? <AttentionCard attention={attention} /> : null}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
