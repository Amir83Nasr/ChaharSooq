import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { FlaskConical, Sparkles } from "lucide-react"

import { AISettingsForm } from "@/components/settings/ai-settings-form"
import { AITestPanel } from "@/components/settings/ai-test-panel"
import { SettingsSection } from "@/components/settings/settings-section"
import { getSessionAdmin } from "@/lib/auth"
import { isOwner } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — هوش مصنوعی" }

export default async function AISettingsPage() {
  const user = await getSessionAdmin()
  if (!user || !isOwner(user.role)) redirect("/settings")

  return (
    <>
      <SettingsSection
        icon={Sparkles}
        title="اتصال به سرویس هوش مصنوعی"
        description="آدرس پایه، کلید API، شناسه مدل و دستور سیستمی مشترک (فقط سوپرادمین)"
      >
        <AISettingsForm />
      </SettingsSection>
      <SettingsSection
        icon={FlaskConical}
        title="آزمایش اتصال"
        description="ارسال یک درخواست واقعی و مشاهده پاسخ مدل"
      >
        <AITestPanel />
      </SettingsSection>
    </>
  )
}
