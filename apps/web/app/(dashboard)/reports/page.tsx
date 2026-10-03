import type { Metadata } from "next"

import { EmptyState } from "@workspace/ui/components/state"
import { PageHeader } from "@workspace/ui/components/page-header"

export const metadata: Metadata = { title: "گزارش‌ها | چهارسوق" }

export default function ReportsPage() {
  return (
    <>
      <PageHeader title="گزارش‌ها" subtitle="گزارش فروش و عملکرد" />
      <EmptyState
        title="گزارشی وجود ندارد"
        hint="پس از ثبت فروش، گزارش‌ها اینجا نمایش داده می‌شوند."
      />
    </>
  )
}
