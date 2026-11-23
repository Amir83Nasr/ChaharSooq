import type { Metadata } from "next"
import { Sigma } from "lucide-react"

import { SettingsSection } from "@/components/settings/settings-section"
import { SuggestedPriceSettings } from "@/components/settings/suggested-price-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — قیمت‌گذاری" }

export default function PricingSettingsPage() {
  return (
    <SettingsSection
      icon={Sigma}
      title="قیمت پیشنهادی"
      description="وزن سهم قیمت رقیب برای هر دسته‌بندی (۰ تا ۱) با پیش‌نمایش زنده"
    >
      <SuggestedPriceSettings />
    </SettingsSection>
  )
}
