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
import { HeaderDateTime } from "@/components/header-datetime"

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
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 overflow-hidden border-b bg-background/80 backdrop-blur-sm md:rounded-t-xl">
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden px-3 sm:px-4">
        <SidebarTrigger className="-ms-1 shrink-0" />
        <span className="me-2 hidden shrink-0 items-center min-[420px]:flex">
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
      <div className="flex shrink-0 items-center gap-1.5 px-3 sm:gap-2 sm:px-4">
        <ThemeToggle />
        <div className="hidden sm:block">
          <HeaderDateTime />
        </div>
      </div>
    </header>
  )
}
