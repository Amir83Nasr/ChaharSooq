"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Fragment } from "react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@workspace/ui/primitives/breadcrumb"

const breadcrumbLabels: Record<string, string> = {
  dashboard: "داشبورد",
  products: "محصولات",
  reports: "گزارش‌ها",
  settings: "تنظیمات",
  pricing: "قیمت‌گذاری",
  sync: "همگام‌سازی",
  inventory: "انبار",
  appearance: "نمایش",
  integrations: "اتصال فروشگاه‌ها",
  sofa: "سوفا",
  digifresh: "دیجی‌فرش",
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
}

export function DashboardBreadcrumbs() {
  const pathname = usePathname()
  const segments = pathname.split("/").filter(Boolean)
  const crumbs = segments.map((seg, i) => ({
    label: breadcrumbLabels[seg] ?? seg,
    href: "/" + segments.slice(0, i + 1).join("/"),
  }))

  return (
    <Breadcrumb dir="rtl" className="min-w-0">
      <BreadcrumbList className="flex-nowrap [&_a]:truncate [&_span]:truncate [&>li]:min-w-0">
        {crumbs.map((crumb, i) => (
          <Fragment key={crumb.href}>
            <BreadcrumbItem>
              {i < crumbs.length - 1 ? (
                <BreadcrumbLink render={<Link href={crumb.href} />}>
                  {crumb.label}
                </BreadcrumbLink>
              ) : (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
            {i < crumbs.length - 1 && <BreadcrumbSeparator />}
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
