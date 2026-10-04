import type { Metadata } from "next"

import { MoonStar, PackageMinus } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { PageHeader } from "@workspace/ui/components/page-header"

import { InventoryThresholdSettings } from "@/components/inventory-threshold-settings"
import { ThemeSettings } from "@/components/theme-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات" }

export default function SettingsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="تنظیمات" subtitle="پیکربندی فروشگاه" />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MoonStar className="size-4" />
            تم نمایش
          </CardTitle>
          <CardDescription>
            روشن، تیره یا همگام با سیستم‌عامل
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ThemeSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PackageMinus className="size-4" />
            آستانه موجودی کم
          </CardTitle>
          <CardDescription>
            از چه موجودی به پایین، کالا «کم» محسوب شود
          </CardDescription>
        </CardHeader>
        <CardContent>
          <InventoryThresholdSettings />
        </CardContent>
      </Card>
    </div>
  )
}
