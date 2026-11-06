import type { Metadata } from "next"
import { Clock } from "lucide-react"

import { CompetitorSyncIntervalSettings } from "@/components/settings/competitor-sync-interval-settings"
import { SettingsSection } from "@/components/settings/settings-section"
import { SyncIntervalSettings } from "@/components/settings/sync-interval-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — همگام‌سازی" }

export default function SyncSettingsPage() {
  return (
    <>
      <SettingsSection
        icon={Clock}
        title="فاصله به‌روزرسانی خودکار"
        description="هر چند ساعت یکبار کاتالوگ محصولات از حسابداری به‌روز شود"
      >
        <SyncIntervalSettings />
      </SettingsSection>
      <SettingsSection
        icon={Clock}
        title="فاصله به‌روزرسانی خودکار قیمت رقبا"
        description="هر چند ساعت یکبار قیمت همه فروشگاه‌های دیگر به‌طور خودکار به‌روز شود؛ فاصله کمتر فشار بیشتر روی فروشگاه‌ها می‌آورد"
      >
        <CompetitorSyncIntervalSettings />
      </SettingsSection>
    </>
  )
}
