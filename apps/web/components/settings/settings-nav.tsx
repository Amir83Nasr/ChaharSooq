"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutGrid,
  PackageMinus,
  Palette,
  RefreshCw,
  Sigma,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

type SettingsNavItem = {
  href: string
  label: string
  icon: LucideIcon
  exact?: boolean
}

const ITEMS: SettingsNavItem[] = [
  { href: "/settings", label: "نمای کلی", icon: LayoutGrid, exact: true },
  { href: "/settings/pricing", label: "قیمت‌گذاری", icon: Sigma },
  { href: "/settings/sync", label: "همگام‌سازی", icon: RefreshCw },
  { href: "/settings/inventory", label: "انبار", icon: PackageMinus },
  { href: "/settings/appearance", label: "نمایش", icon: Palette },
]

function isActive(item: SettingsNavItem, pathname: string): boolean {
  return item.exact
    ? pathname === item.href
    : pathname === item.href || pathname.startsWith(`${item.href}/`)
}

/**
 * In-settings navigation: a sticky column on desktop and a horizontally
 * scrollable chip row on mobile, so the settings map is always one tap away.
 */
export function SettingsNav() {
  const pathname = usePathname()

  return (
    <nav
      aria-label="بخش‌های تنظیمات"
      className="min-w-0 md:sticky md:top-16 md:self-start"
    >
      <ul className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1 md:flex-col md:items-stretch md:overflow-visible md:pb-0">
        {ITEMS.map((item) => {
          const active = isActive(item, pathname)
          return (
            <li key={item.href} className="shrink-0 md:shrink">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex h-10 items-center gap-2 rounded-2xl border px-3 text-sm font-medium whitespace-nowrap transition-[color,background-color,border-color,box-shadow] outline-none focus-visible:ring-2 focus-visible:ring-ring md:w-full",
                  active
                    ? "border-primary bg-primary text-primary-foreground shadow-sm"
                    : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                <item.icon className="size-4 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
