import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { LoginShell } from "@/components/login-shell"
import { getSessionAdmin } from "@/lib/auth"

export const metadata: Metadata = {
  title: "ورود مدیر | چهارسوق",
  description: "ورود به پنل مدیریت فروشگاه چهارسوق",
}

export default async function LoginPage() {
  const admin = await getSessionAdmin()
  if (admin) redirect("/dashboard")
  return <LoginShell />
}
