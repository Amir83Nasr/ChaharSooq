"use client"

import { useEffect, useState } from "react"
import { PackageMinus, Palette, RefreshCw, Sigma } from "lucide-react"

import { formatPersianNumber } from "@workspace/ui/lib/number"

import { api, type SettingsOut } from "@/lib/api"
import { SettingsOverviewCard } from "@/components/settings/settings-overview-card"

const STORE_LABELS: Record<SettingsOut["default_competitor_store"], string> = {
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
}

function intervalLabel(minutes: number): string {
  const hours = minutes / 60
  const display = Number.isInteger(hours)
    ? formatPersianNumber(hours)
    : formatPersianNumber(Number(hours.toFixed(1)))
  return `هر ${display} ساعت`
}

export function SettingsOverview() {
  const [settings, setSettings] = useState<SettingsOut | null>(null)

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
                STORE_LABELS[settings.default_competitor_store]
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
    </div>
  )
}
