import type { Metadata } from "next"
import { Sigma, Store } from "lucide-react"

import { CompetitorStoreSettings } from "@/components/settings/competitor-store-settings"
import { SettingsSection } from "@/components/settings/settings-section"
import { SuggestedPriceSettings } from "@/components/settings/suggested-price-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — قیمت‌گذاری" }

export default function PricingSettingsPage() {
  return (
    <>
      <SettingsSection
        icon={Sigma}
        title="قیمت پیشنهادی"
        description="وزن سهم قیمت رقیب برای هر دسته‌بندی (۰ تا ۱) با پیش‌نمایش زنده"
      >
        <SuggestedPriceSettings />
      </SettingsSection>
      <SettingsSection
        icon={Store}
        title="بازار پیش‌فرض قیمت رقبا"
        description="در جدول محصولات، ستون «قیمت رقبا» اول قیمت کدام فروشگاه را نشان بدهد؛ تغییر بازار در هدر جدول موقتی است"
      >
        <CompetitorStoreSettings />
      </SettingsSection>
    </>
  )
}
