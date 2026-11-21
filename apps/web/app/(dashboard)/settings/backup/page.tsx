import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { Database, History } from "lucide-react"

import { BackupList } from "@/components/settings/backup-list"
import { BackupSettingsForm } from "@/components/settings/backup-settings"
import { SettingsSection } from "@/components/settings/settings-section"
import { getSessionAdmin } from "@/lib/auth"
import { isOwner } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — پشتیبان" }

export default async function BackupSettingsPage() {
  const user = await getSessionAdmin()
  if (!user || !isOwner(user.role)) redirect("/settings")

  return (
    <>
      <SettingsSection
        icon={Database}
        title="پشتیبان خودکار"
        description="روشن یا خاموش کردن و تعیین فاصلهٔ ساخت نسخهٔ خودکار."
      >
        <BackupSettingsForm />
      </SettingsSection>
      <SettingsSection
        icon={History}
        title="مدیریت پشتیبان و بازیابی"
        description="ساخت، بارگذاری، دانلود، بازیابی و حذف نسخه."
      >
        <BackupList />
      </SettingsSection>
    </>
  )
}
