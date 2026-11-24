import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { Sigma } from "lucide-react"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { SettingsSection } from "@/components/settings/settings-section"
import { SuggestedPriceSettings } from "@/components/settings/suggested-price-settings"
import { getSessionAdmin } from "@/lib/auth"
import { isAdmin } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | قیمت‌گذاری" }

export default async function PricingPage() {
  const user = await getSessionAdmin()
  if (!user) redirect("/login")
  // Pricing is shop-wide configuration, so viewers never reach it.
  if (!isAdmin(user.role)) redirect("/products")

  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      <PageHeader
        title="قیمت‌گذاری"
        subtitle="تعیین وزن منابع قیمت و نحوه محاسبه قیمت پیشنهادی کالاها"
      />
      <SettingsSection
        icon={Sigma}
        title="روش تعیین قیمت"
        description="وزن سهم منبع قیمت به‌ازای هر بخش کاتالوگ (۰ تا ۱)؛ مشترک بین هر دو فرمول، و هر کالا حالت خود را انتخاب می‌کند."
      >
        <SuggestedPriceSettings />
      </SettingsSection>
    </div>
  )
}
