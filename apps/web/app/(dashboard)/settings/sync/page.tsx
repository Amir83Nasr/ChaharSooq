import type { Metadata } from "next"
import { Clock, Plug } from "lucide-react"

import { CompetitorSyncIntervalSettings } from "@/components/settings/competitor-sync-interval-settings"
import { ParsinaConnectionSettings } from "@/components/settings/parsina-connection-settings"
import { SettingsSection } from "@/components/settings/settings-section"
import { SyncIntervalSettings } from "@/components/settings/sync-interval-settings"
import { getSessionAdmin } from "@/lib/auth"
import { isOwner } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — همگام‌سازی" }

export default async function SyncSettingsPage() {
  const user = await getSessionAdmin()
  const owner = user ? isOwner(user.role) : false

  return (
    <>
      {owner ? (
        <SettingsSection
          icon={Plug}
          title="اتصال به پارسینا"
          description="مشخصات اتصال به وب‌سرویس حسابداری پارسینا (فقط سوپرادمین)"
        >
          <ParsinaConnectionSettings />
        </SettingsSection>
      ) : null}
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
