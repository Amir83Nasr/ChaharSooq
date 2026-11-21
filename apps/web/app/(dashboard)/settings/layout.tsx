import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { SettingsNav } from "@/components/settings/settings-nav"
import { getSessionAdmin } from "@/lib/auth"
import { isAdmin, isOwner } from "@/lib/session"

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
  const owner = isOwner(user.role)
  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      {/* Keep the title under the 4rem glass header while only the content
          column scrolls. Sticky offsets include the scroll area's 5rem top
          padding, so -1rem aligns the band just below the header. Mobile keeps
          the plain, non-sticky header. */}
      <div className="sticky-page-band md:sticky md:-top-4 md:z-20 md:-mx-4 md:flex md:h-16 md:items-center md:px-4">
        <PageHeader title="تنظیمات" subtitle="پیکربندی فروشگاه" />
      </div>
      <div className="grid gap-4 md:grid-cols-[13rem_minmax(0,1fr)] md:gap-6">
        <SettingsNav owner={owner} />
        <div className="flex min-w-0 flex-col gap-4">{children}</div>
      </div>
    </div>
  )
}
