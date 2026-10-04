"use client"

import Link from "next/link"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@workspace/ui/components/breadcrumb"
import { Separator } from "@workspace/ui/components/separator"
import { SidebarTrigger } from "@workspace/ui/components/sidebar"
import { usePathname } from "next/navigation"
import { Fragment } from "react"

import { ThemeToggle } from "@/components/theme-toggle"

const breadcrumbLabels: Record<string, string> = {
  dashboard: "داشبورد",
  products: "محصولات",
  reports: "گزارش‌ها",
  settings: "تنظیمات",
}

export function DashboardHeader() {
  const pathname = usePathname()
  const segments = pathname.split("/").filter(Boolean)
  const crumbs = segments.map((seg, i) => ({
    label: breadcrumbLabels[seg] ?? seg,
    href: "/" + segments.slice(0, i + 1).join("/"),
  }))

  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur-sm">
      <div className="flex min-w-0 items-center gap-2 px-3 sm:px-4">
        <SidebarTrigger className="-ms-1" />
        <span className="me-2 flex items-center">
          <Separator orientation="vertical" className="h-4" />
        </span>
        <Breadcrumb className="min-w-0">
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
      </div>
      <div className="flex-1" />
      <div className="flex shrink-0 items-center gap-1.5 px-3 sm:gap-2 sm:px-4">
        <ThemeToggle />
      </div>
    </header>
  )
}
