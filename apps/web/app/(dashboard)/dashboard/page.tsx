import type { Metadata } from "next"

import { DashboardView } from "./_components/dashboard-view"

export const metadata: Metadata = { title: "چهارسوق | داشبورد" }

export default function DashboardPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <DashboardView />
    </div>
  )
}
