import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { Sparkles } from "lucide-react"

import { AISettingsForm } from "@/components/settings/ai-settings-form"
import { SettingsSection } from "@/components/settings/settings-section"
import { getSessionAdmin } from "@/lib/auth"
import { isAdmin } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — هوش مصنوعی" }

export default async function AISettingsPage() {
  const user = await getSessionAdmin()
  if (!user || !isAdmin(user.role)) redirect("/settings")

  return (
    <SettingsSection
      icon={Sparkles}
      title="اتصال به سرویس هوش مصنوعی"
      description="آدرس پایه، کلید API، شناسه مدل و دستور سیستمی مشترک"
    >
      <AISettingsForm />
    </SettingsSection>
  )
}
