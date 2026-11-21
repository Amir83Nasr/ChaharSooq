import type { Metadata } from "next"

import { SettingsOverview } from "@/components/settings/settings-overview"
import { getSessionAdmin } from "@/lib/auth"
import { isOwner } from "@/lib/session"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات" }

export default async function SettingsPage() {
  const user = await getSessionAdmin()
  return <SettingsOverview owner={user ? isOwner(user.role) : false} />
}
