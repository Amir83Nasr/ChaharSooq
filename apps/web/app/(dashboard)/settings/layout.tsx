import type { Metadata } from "next"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { SettingsNav } from "@/components/settings/settings-nav"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات" }

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      <PageHeader title="تنظیمات" subtitle="پیکربندی فروشگاه" />
      <div className="grid gap-4 md:grid-cols-[13rem_minmax(0,1fr)] md:gap-6">
        <SettingsNav />
        <div className="flex min-w-0 flex-col gap-4">{children}</div>
      </div>
    </div>
  )
}
