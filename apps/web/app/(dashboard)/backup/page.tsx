import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { Database, History } from "lucide-react"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { BackupList } from "@/components/settings/backup-list"
import { BackupSettingsForm } from "@/components/settings/backup-settings"
import { SettingsSection } from "@/components/settings/settings-section"
import { getSessionAdmin } from "@/lib/auth"
import { isOwner } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | پشتیبان‌گیری" }

export default async function BackupPage() {
  const user = await getSessionAdmin()
  if (!user || !isOwner(user.role)) redirect("/settings")

  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      <PageHeader
        title="پشتیبان‌گیری"
        subtitle="تهیه، نگهداری و بازیابی نسخه پشتیبان از داده‌ها"
      />
      <SettingsSection
        icon={Database}
        title="پشتیبان خودکار"
        description="روشن یا خاموش کردن و تعیین فاصله ساخت نسخه خودکار."
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
    </div>
  )
}
