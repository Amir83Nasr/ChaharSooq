import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { PageHeader } from "@workspace/ui/layout/page-header"

import { getSessionAdmin } from "@/lib/auth"
import { UsersView } from "./_components/users-view"

export const metadata: Metadata = { title: "چهارسوق | کاربران" }

export default async function UsersPage() {
  const user = await getSessionAdmin()
  if (!user) redirect("/login")
  if (user.role !== "admin") redirect("/products")
  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      <PageHeader
        title="کاربران"
        subtitle="ساخت و حذف حساب‌ها و تعیین سطح دسترسی"
      />
      <UsersView currentUsername={user.username} />
    </div>
  )
}
