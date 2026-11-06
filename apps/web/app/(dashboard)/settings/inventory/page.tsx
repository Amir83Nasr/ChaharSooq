import type { Metadata } from "next"
import { PackageMinus } from "lucide-react"

import { InventoryThresholdSettings } from "@/components/settings/inventory-threshold-settings"
import { SettingsSection } from "@/components/settings/settings-section"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — انبار" }

export default function InventorySettingsPage() {
  return (
    <SettingsSection
      icon={PackageMinus}
      title="آستانه موجودی کم"
      description="از چه موجودی به پایین، کالا «کم» محسوب شود"
    >
      <InventoryThresholdSettings />
    </SettingsSection>
  )
}
