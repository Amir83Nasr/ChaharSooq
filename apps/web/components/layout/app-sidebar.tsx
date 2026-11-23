"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Database,
  LayoutDashboard,
  Package,
  Settings,
  Sparkles,
  Store,
  UsersRound,
  X,
  type LucideIcon,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@workspace/ui/primitives/sidebar"
import { Badge } from "@workspace/ui/primitives/badge"
import { Button } from "@workspace/ui/primitives/button"
import { LogoutMenuItem } from "@/components/auth/logout-menu-item"
import { useSession } from "@/components/auth/session-provider"
import { prefetchProducts } from "@/lib/products-store"
import { isOwner } from "@/lib/session"

type NavLinkItem = {
  kind: "link"
  href: string
  label: string
  icon: LucideIcon
  soon?: boolean
  ownerOnly?: boolean
}

// Disabled entry: shown for orientation; implementation is planned.
type NavInfoItem = {
  kind: "info"
  label: string
  icon: LucideIcon
  tag: string
}

type NavItem = NavLinkItem | NavInfoItem

type NavGroup = {
  group: string
  items: NavItem[]
}

const NAV: NavGroup[] = [
  {
    group: "اصلی",
    items: [
      { kind: "link", href: "/products", label: "محصولات", icon: Package },
      {
        kind: "link",
        href: "/dashboard",
        label: "داشبورد",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    group: "فروشگاه‌ها",
    items: [
      {
        kind: "info",
        label: "اتصال فروشگاه‌ها",
        icon: Store,
        tag: "به‌زودی",
      },
    ],
  },
  {
    group: "هوش مصنوعی",
    items: [
      {
        kind: "link",
        href: "/ai-assistant",
        label: "دستیار هوشمند",
        icon: Sparkles,
        soon: true,
      },
    ],
  },
  {
    group: "سیستم",
    items: [
      { kind: "link", href: "/settings", label: "تنظیمات", icon: Settings },
      {
        kind: "link",
        href: "/backup",
        label: "پشتیبان‌گیری",
        icon: Database,
        ownerOnly: true,
      },
      { kind: "link", href: "/users", label: "کاربران", icon: UsersRound },
    ],
  },
]

function isLinkActive(href: string, pathname: string) {
  return href === "/dashboard"
    ? pathname === href
    : pathname === href || pathname.startsWith(`${href}/`)
}

// Shared presentation for entries that are visible but not yet implemented.
function DisabledNavItem({
  icon: Icon,
  label,
  tag,
}: {
  icon: LucideIcon
  label: string
  tag: string
}) {
  return (
    <SidebarMenuItem aria-hidden={false}>
      <div className="relative">
        <SidebarMenuButton
          render={
            <span
              aria-disabled="true"
              tabIndex={-1}
              aria-label={`${label} — ${tag}`}
              className="opacity-60"
            >
              <Icon className="sidebar-collapse-icon" />
              <span className="sidebar-collapse-label">{label}</span>
            </span>
          }
          tooltip={`${label} — ${tag}`}
        />
        <Badge
          variant="secondary"
          className="sidebar-collapse-fade inset-e-2 absolute top-1/2 h-5 -translate-y-1/2 px-1.5 text-[10px]"
        >
          {tag}
        </Badge>
      </div>
    </SidebarMenuItem>
  )
}

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()
  const { isMobile, setOpenMobile } = useSidebar()
  const { canManage, role } = useSession()
  // Views that only make sense for the full-management role. Backup stays
  // owner-only even among management accounts, matching the page guard.
  const nav = (canManage ? NAV : NAV.filter((group) => group.group !== "سیستم"))
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !("ownerOnly" in item && item.ownerOnly) || isOwner(role)
      ),
    }))
    .filter((group) => group.items.length > 0)

  const closeMobileSidebar = () => {
    if (isMobile) setOpenMobile(false)
  }

  // Warm the catalog on intent so the first visit is not a cold skeleton.
  // No-op once the store already holds a page.
  const warmProducts = () => {
    void prefetchProducts()
  }

  return (
    <Sidebar collapsible="offcanvas" side="right" {...props}>
      <SidebarHeader>
        {/* Desktop: full brand lockup with subtitle. Hidden on mobile. */}
        <div className="hidden items-center gap-2.5 px-0 py-1 transition-[gap] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-data-[collapsible=icon]:gap-0 motion-reduce:transition-none md:flex">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary via-primary to-primary/65 text-lg font-black text-primary-foreground shadow-sm ring-1 ring-foreground/10">
            چ
          </span>
          <span className="sidebar-collapse-label flex min-w-0 flex-col gap-0.5">
            <span className="text-[15px] leading-5 font-extrabold tracking-tight">
              چهارسوق
            </span>
            <span className="text-[11px] leading-4 text-muted-foreground">
              پنل مدیریت فروشگاه
            </span>
          </span>
        </div>
        {/* Mobile (ChatGPT-app style): flat single-line brand + explicit
            close affordance. The sheet hides its default close button, so
            this X is the only dismiss control besides the scrim. */}
        <div className="flex items-center justify-between px-1 py-1 md:hidden">
          <Link
            href="/dashboard"
            onClick={closeMobileSidebar}
            aria-label="چهارسوق — رفتن به داشبورد"
            className="flex min-w-0 items-center gap-2.5 rounded-full"
          >
            <span
              aria-hidden="true"
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-foreground text-sm font-bold text-background"
            >
              چ
            </span>
            <span className="truncate text-[15px] leading-5 font-semibold tracking-tight">
              چهارسوق
            </span>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={closeMobileSidebar}
            aria-label="بستن منو"
            className="size-9 shrink-0 rounded-full"
          >
            <X className="size-5" aria-hidden="true" />
            <span className="sr-only">بستن منو</span>
          </Button>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {nav.map((entry) => (
          <SidebarGroup key={entry.group}>
            <SidebarGroupLabel>{entry.group}</SidebarGroupLabel>
            <SidebarMenu>
              {entry.items.map((item) =>
                item.kind === "info" ? (
                  <DisabledNavItem
                    key={item.label}
                    icon={item.icon}
                    label={item.label}
                    tag={item.tag}
                  />
                ) : item.soon ? (
                  <DisabledNavItem
                    key={item.href}
                    icon={item.icon}
                    label={item.label}
                    tag="به‌زودی"
                  />
                ) : (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      render={
                        <Link
                          href={item.href}
                          prefetch={
                            item.href === "/products" ? true : undefined
                          }
                          onPointerEnter={
                            item.href === "/products" ? warmProducts : undefined
                          }
                          onFocus={
                            item.href === "/products" ? warmProducts : undefined
                          }
                          onClick={closeMobileSidebar}
                        >
                          <item.icon className="sidebar-collapse-icon" />
                          <span className="sidebar-collapse-label">
                            {item.label}
                          </span>
                        </Link>
                      }
                      tooltip={item.label}
                      isActive={isLinkActive(item.href, pathname)}
                    />
                  </SidebarMenuItem>
                )
              )}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <LogoutMenuItem />
      </SidebarFooter>
    </Sidebar>
  )
}
