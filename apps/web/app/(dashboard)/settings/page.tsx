import type { Metadata } from "next"

import { PageHeader } from "@workspace/ui/components/page-header"

export const metadata: Metadata = { title: "تنظیمات | چهارسوق" }

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="تنظیمات" subtitle="پیکربندی فروشگاه" />
      <p className="text-sm text-muted-foreground">
        تنظیمات در ادامه پیاده‌سازی می‌شود.
      </p>
    </>
  )
}
