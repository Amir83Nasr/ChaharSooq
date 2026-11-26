import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { SettingsNav } from "@/components/settings/settings-nav"
import { getSessionAdmin } from "@/lib/auth"
import { isAdmin } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات" }

export default async function SettingsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getSessionAdmin()
  if (!user) redirect("/login")
  // Settings change shop-wide behaviour, so the read-only role never sees them.
  if (!isAdmin(user.role)) redirect("/products")
  return (
    <div className="flex flex-1 flex-col">
      {/* Start column (right in RTL) holds the title and the in-settings nav
          and sticks as one unit: the main column on the left starts at the
          top edge and scrolls on its own instead of waiting below a
          full-width title band. Sticky offsets include the scroll area's
          5rem top padding, so -1rem parks the title just below the 4rem
          glass header. The column carries no background: nothing scrolls
          under it, so the shared grid layer stays visible and aligned.
          Mobile keeps the plain, non-sticky stack. */}
      <div className="grid gap-4 md:grid-cols-[13rem_minmax(0,1fr)] md:gap-6">
        <div className="flex min-w-0 flex-col gap-4 md:sticky md:-top-4 md:z-20 md:self-start">
          <div className="md:flex md:h-16 md:items-center">
            <PageHeader title="تنظیمات" subtitle="پیکربندی فروشگاه" />
          </div>
          <SettingsNav />
        </div>
        <div className="flex min-w-0 flex-col gap-4">{children}</div>
      </div>
    </div>
  )
}
