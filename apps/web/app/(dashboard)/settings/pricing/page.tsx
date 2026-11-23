import type { Metadata } from "next"
import { Sigma } from "lucide-react"

import { SettingsSection } from "@/components/settings/settings-section"
import { SuggestedPriceSettings } from "@/components/settings/suggested-price-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — قیمت‌گذاری" }

export default function PricingSettingsPage() {
  return (
    <SettingsSection
      icon={Sigma}
      title="روش تعیین قیمت"
      description="وزن سهم منبع قیمت برای هر حالت قیمت‌گذاری (۰ تا ۱)؛ هر کالا حالت خود را انتخاب می‌کند."
    >
      <SuggestedPriceSettings />
    </SettingsSection>
  )
}
