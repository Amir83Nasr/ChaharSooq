import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowUpRight, CircleHelp } from "lucide-react"

import { PageHeader } from "@workspace/ui/components/page-header"
import { Button } from "@workspace/ui/components/button"

const STORES = {
  sofa: {
    name: "سوفا",
    category: "مبلمان",
    description: "قیمت محصولات مبلمان در سوفا با قیمت فروشگاه مقایسه می‌شود.",
  },
  digifresh: {
    name: "دیجی‌فرش",
    category: "فرش",
    description: "قیمت محصولات فرش در دیجی‌فرش با قیمت فروشگاه مقایسه می‌شود.",
  },
  digikala: {
    name: "دیجی‌کالا",
    category: "لوازم خانگی",
    description: "قیمت لوازم خانگی در دیجی‌کالا با قیمت فروشگاه مقایسه می‌شود.",
  },
  technolife: {
    name: "تکنولایف",
    category: "لوازم خانگی",
    description: "قیمت لوازم خانگی در تکنولایف با قیمت فروشگاه مقایسه می‌شود.",
  },
} as const

type StoreKey = keyof typeof STORES

export default async function IntegrationPage({
  params,
}: {
  params: Promise<{ store: string }>
}) {
  const { store } = await params
  if (!(store in STORES)) notFound()
  const integration = STORES[store as StoreKey]
  const linkCheckEnabled = store === "digikala" || store === "technolife"

  return (
    <>
      <PageHeader
        title={`اتصال ${integration.name}`}
        subtitle={integration.description}
      />
      <section className="w-full space-y-4 rounded-lg border border-border bg-muted/40 p-5">
        <div className="flex items-start gap-3">
          <CircleHelp className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div className="space-y-1">
            <h2 className="font-semibold">
              {linkCheckEnabled
                ? "بررسی قیمت از صفحهٔ کالا"
                : "این منبع هنوز فعال نشده است"}
            </h2>
            <p className="text-sm leading-6 text-muted-foreground">
              {linkCheckEnabled
                ? `برای کالاهای لوازم خانگی، جزئیات کالا را در فهرست محصولات باز کنید و لینک صفحهٔ ${integration.name} را ثبت یا بررسی کنید. قیمت تازهٔ لینک در جدول نمایش داده می‌شود؛ اگر استخراج ممکن نباشد، خطا و فرم ثبت دستی در همان بخش در دسترس است.`
                : `اتصال ${integration.name} در فاز بعدی پیاده‌سازی می‌شود. گروه کالای این منبع: ${integration.category}.`}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <p className="text-sm text-muted-foreground">
            گروه کالا: {integration.category}
          </p>
          <Button nativeButton={false} render={<Link href="/products" />}>
            دیدن کالاها <ArrowUpRight aria-hidden="true" />
          </Button>
        </div>
      </section>
    </>
  )
}
