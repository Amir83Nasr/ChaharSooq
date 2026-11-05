import Link from "next/link"
import { ArrowUpRight } from "lucide-react"

import { PageHeader } from "@workspace/ui/layout/page-header"
import { Badge } from "@workspace/ui/primitives/badge"
import { Button } from "@workspace/ui/primitives/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"

import { STORES } from "./_components/store-config"

const STORE_ORDER = ["sofa", "digifresh", "digikala", "technolife"] as const

export default function IntegrationsPage() {
  return (
    <>
      <PageHeader
        title="اتصال فروشگاه‌ها"
        subtitle="مقایسه قیمت فروشگاه با هر منبع؛ برای جزئیات وارد صفحه هر فروشگاه شوید."
      />
      <div className="grid gap-4 md:grid-cols-2">
        {STORE_ORDER.map((key) => {
          const store = STORES[key]
          return (
            <Card key={store.key}>
              <CardHeader className="flex flex-row flex-wrap items-center gap-2">
                <CardTitle>{store.name}</CardTitle>
                <span className="ms-auto flex flex-wrap gap-1.5">
                  <Badge variant="secondary">{store.topGroup}</Badge>
                  <Badge variant={store.auto ? "default" : "outline"}>
                    {store.auto ? "بررسی خودکار" : "فهرست گروه"}
                  </Badge>
                </span>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  {store.description}
                </p>
                <div>
                  <Button
                    nativeButton={false}
                    variant="outline"
                    className="h-11 w-full md:h-9 md:w-auto"
                    render={<Link href={`/integrations/${store.key}`} />}
                  >
                    مشاهده اتصال
                    <ArrowUpRight aria-hidden="true" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </>
  )
}
