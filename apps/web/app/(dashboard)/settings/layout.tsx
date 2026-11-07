import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { SettingsNav } from "@/components/settings/settings-nav"
import { getSessionAdmin } from "@/lib/auth"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات" }

export default async function SettingsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getSessionAdmin()
  if (!user) redirect("/login")
  // Settings change shop-wide behaviour, so the read-only role never sees them.
  if (user.role !== "admin") redirect("/products")
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
