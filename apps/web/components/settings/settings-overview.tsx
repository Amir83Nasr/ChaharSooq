"use client"

import { useEffect, useState } from "react"
import { Database, PackageMinus, Palette, RefreshCw, Sigma } from "lucide-react"

import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { formatPersianNumber } from "@workspace/ui/lib/number"

import { api, type SettingsOut } from "@/lib/api"
import { STORE_MARKET_LABELS } from "@/lib/competitor-price"
import { SettingsOverviewCard } from "@/components/settings/settings-overview-card"

function intervalLabel(minutes: number): string {
  const hours = minutes / 60
  const display = Number.isInteger(hours)
    ? formatPersianNumber(hours)
    : formatPersianNumber(Number(hours.toFixed(1)))
  return `هر ${display} ساعت`
}

export function SettingsOverview({ owner }: { owner: boolean }) {
  const [settings, setSettings] = useState<SettingsOut | null>(null)
  const [lastBackup, setLastBackup] = useState<string | null>(null)

  useEffect(() => {
    if (!owner) return
    let cancelled = false
    api
      .backups()
      .then((rows) => {
        if (cancelled) return
        const verified = rows.find((row) => row.verification === "verified")
        setLastBackup(
          verified ? formatPersianDateTime(verified.created_at) : null
        )
      })
      .catch(() => {
        // The overview card keeps its static description when the list fails.
      })
    return () => {
      cancelled = true
    }
  }, [owner])

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (!cancelled) setSettings(data)
      })
      .catch(() => {
        // The cards keep their static descriptions when the summary fails.
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <SettingsOverviewCard
        href="/settings/pricing"
        icon={Sigma}
        title="قیمت‌گذاری"
        description="وزن سهم قیمت رقیب برای هر دسته‌بندی و بازار پیش‌فرض قیمت رقبا"
        summary={
          settings
            ? `${formatPersianNumber(settings.suggested_price_formulas.length)} دسته‌بندی وزن‌دار · بازار پیش‌فرض: ${
                STORE_MARKET_LABELS[settings.default_competitor_store]
              }`
            : "وزن فرمول‌های قیمت پیشنهادی و بازار پیش‌فرض رقبا"
        }
      />
      <SettingsOverviewCard
        href="/settings/sync"
        icon={RefreshCw}
        title="همگام‌سازی"
        description="فاصله به‌روزرسانی خودکار کاتالوگ محصولات و قیمت رقبا"
        summary={
          settings
            ? `کاتالوگ: ${intervalLabel(settings.sync_interval_minutes)} · رقبا: ${intervalLabel(
                settings.competitor_sync_interval_minutes
              )}`
            : "فاصله به‌روزرسانی کاتالوگ و قیمت رقبا"
        }
      />
      <SettingsOverviewCard
        href="/settings/inventory"
        icon={PackageMinus}
        title="انبار"
        description="آستانه موجودی کم برای هشدار کالاهای رو به اتمام"
        summary={
          settings
            ? `از موجودی ${formatPersianNumber(settings.low_stock_threshold)} به پایین، کالا «کم» محسوب می‌شود`
            : "آستانه موجودی کم"
        }
      />
      <SettingsOverviewCard
        href="/settings/appearance"
        icon={Palette}
        title="نمایش"
        description="تم، تعداد ردیف جدول و ستون‌های جدول محصولات"
        summary="ظاهر پنل و چیدمان جدول محصولات را تنظیم کنید"
      />
      {owner ? (
        <SettingsOverviewCard
          href="/settings/backup"
          icon={Database}
          title="پشتیبان‌گیری"
          description="پشتیبان‌گیری دستی و خودکار از پایگاه داده، بارگذاری نسخه، دانلود و بازیابی"
          summary={
            lastBackup
              ? `آخرین پشتیبان تأیید‌شده: ${lastBackup}`
              : "ساخت، بارگذاری و بازیابی نسخه پشتیبان (فقط سوپرادمین)"
          }
        />
      ) : null}
    </div>
  )
}
