import type { Metadata } from "next"

import { PageHeader } from "@workspace/ui/components/page-header"
import { EmptyState } from "@workspace/ui/components/state"

export const metadata: Metadata = { title: "چهارسوق | گزارش‌ها" }

export default function ReportsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="گزارش‌ها" subtitle="گزارش فروش و عملکرد" />
      <EmptyState
        title="گزارشی ثبت نشده است"
        hint="پس از ثبت فروش، گزارش‌ها در این بخش نمایش داده می‌شوند."
      />
    </div>
  )
}
