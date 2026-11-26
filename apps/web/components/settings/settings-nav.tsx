"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutGrid,
  PackageMinus,
  Palette,
  RefreshCw,
  Sparkles,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

import { useSession } from "@/components/auth/session-provider"
import { isOwner } from "@/lib/session"

type SettingsNavItem = {
  href: string
  label: string
  icon: LucideIcon
  exact?: boolean
  ownerOnly?: boolean
}

const ITEMS: SettingsNavItem[] = [
  { href: "/settings", label: "نمای کلی", icon: LayoutGrid, exact: true },
  { href: "/settings/sync", label: "همگام‌سازی", icon: RefreshCw },
  { href: "/settings/inventory", label: "انبار", icon: PackageMinus },
  { href: "/settings/appearance", label: "نمایش", icon: Palette },
  {
    href: "/settings/ai",
    label: "هوش مصنوعی",
    icon: Sparkles,
    ownerOnly: true,
  },
]

function isActive(item: SettingsNavItem, pathname: string): boolean {
  return item.exact
    ? pathname === item.href
    : pathname === item.href || pathname.startsWith(`${item.href}/`)
}

/**
 * In-settings navigation: a sticky column on desktop and a horizontally
 * scrollable chip row on mobile, so the settings map is always one tap away.
 * On desktop it sits below the sticky title band: the 5rem scroll-area top
 * padding cancels the glass header's 4rem, leaving 4rem title + 1.5rem gap,
 * so the sticky offset is 4.5rem (top-18).
 */
export function SettingsNav() {
  const pathname = usePathname()
  const { role } = useSession()
  const items = ITEMS.filter((item) => !item.ownerOnly || isOwner(role))

  return (
    <nav
      aria-label="بخش‌های تنظیمات"
      className="min-w-0 md:sticky md:top-18 md:self-start"
    >
      <ul className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1 md:flex-col md:items-stretch md:overflow-visible md:pb-0">
        {items.map((item) => {
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
