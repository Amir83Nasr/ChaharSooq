import type { Metadata } from "next"

import { Wrench } from "lucide-react"

import { Card, CardContent } from "@workspace/ui/components/card"
import { PageHeader } from "@workspace/ui/components/page-header"

export const metadata: Metadata = { title: "چهارسوق | داشبورد" }

export default function DashboardPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="داشبورد" subtitle="نمای کلی فروشگاه" />
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-20">
          <div className="mb-6 rounded-full bg-muted p-4">
            <Wrench className="size-12 text-muted-foreground" />
          </div>
          <h3 className="mb-2 text-xl font-semibold">در حال توسعه</h3>
          <p className="max-w-md text-center text-sm text-muted-foreground">
            داشبورد فروشگاه در حال توسعه است. به‌زودی آمارها، نمودارها و
            گزارش‌های جامع‌تری در این بخش در دسترس خواهد بود.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
