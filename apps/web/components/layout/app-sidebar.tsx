"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Bot,
  ChevronDown,
  LayoutDashboard,
  Package,
  Settings,
  Sparkles,
  Store,
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
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@workspace/ui/primitives/sidebar"
import { Badge } from "@workspace/ui/primitives/badge"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { cn } from "@workspace/ui/lib/utils"
import { LogoutMenuItem } from "@/components/auth/logout-menu-item"

type NavChild = {
  href: string
  label: string
}

type NavLinkItem = {
  href: string
  label: string
  icon: LucideIcon
  soon?: boolean
}

type NavParentItem = {
  label: string
  icon: LucideIcon
  children: NavChild[]
}

type NavItem = NavLinkItem | NavParentItem

type NavGroup = {
  group: string
  items: NavItem[]
}

const NAV: NavGroup[] = [
  {
    group: "اصلی",
    items: [
      { href: "/products", label: "محصولات", icon: Package },
      { href: "/dashboard", label: "داشبورد", icon: LayoutDashboard },
    ],
  },
  {
    group: "فروشگاه‌ها",
    items: [
      {
        label: "اتصال فروشگاه‌ها",
        icon: Store,
        children: [
          { href: "/integrations/sofa", label: "سوفا" },
          { href: "/integrations/digifresh", label: "دیجی‌فرش" },
          { href: "/integrations/digikala", label: "دیجی‌کالا" },
          { href: "/integrations/technolife", label: "تکنولایف" },
        ],
      },
    ],
  },
  {
    group: "هوش مصنوعی",
    items: [
      {
        href: "/ai-assistant",
        label: "دستیار هوشمند",
        icon: Sparkles,
        soon: true,
      },
      {
        href: "/ai-pricing",
        label: "قیمت‌گذاری هوشمند",
        icon: Bot,
        soon: true,
      },
    ],
  },
  {
    group: "سیستم",
    items: [{ href: "/settings", label: "تنظیمات", icon: Settings }],
  },
]

// آیتم‌های فازهای بعدی. روت ندارند و رندر نمی‌شوند؛ با ساخته شدن
// روت هر کدام، از اینجا به NAV منتقل می‌شوند.
export const FUTURE_NAV: {
  group: string
  items: { href: string; label: string; soon: true }[]
}[] = [
  {
    group: "فروش",
    items: [
      { href: "/orders", label: "سفارش‌ها", soon: true },
      { href: "/customers", label: "مشتریان", soon: true },
      { href: "/discounts", label: "تخفیف‌ها", soon: true },
    ],
  },
  {
    group: "مدیریت",
    items: [
      { href: "/inventory", label: "موجودی انبار", soon: true },
      { href: "/suppliers", label: "تأمین‌کنندگان", soon: true },
    ],
  },
  {
    group: "سیستم",
    items: [{ href: "/users", label: "کاربران", soon: true }],
  },
]

function isLinkActive(href: string, pathname: string) {
  return href === "/dashboard"
    ? pathname === href
    : pathname === href || pathname.startsWith(`${href}/`)
}

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()
  const { isMobile, setOpenMobile } = useSidebar()
  const storesActive = pathname.startsWith("/integrations")
  const [storesOpen, setStoresOpen] = useState(storesActive)

  useEffect(() => {
    if (storesActive) setStoresOpen(true)
  }, [storesActive])

  const closeMobileSidebar = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <Sidebar collapsible="icon" side="right" {...props}>
      <SidebarHeader className="group-data-[collapsible=icon]:px-0">
        <div className="flex items-center gap-2 px-2 py-1 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground">
            چ
          </span>
          <span className="flex min-w-0 flex-col group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-bold">چهارسوق</span>
            <span className="text-xs text-muted-foreground">
              پنل مدیریت فروشگاه
            </span>
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {NAV.map((entry) => (
          <SidebarGroup
            key={entry.group}
            className="group-data-[collapsible=icon]:px-0"
          >
            <SidebarGroupLabel>{entry.group}</SidebarGroupLabel>
            <SidebarMenu>
              {entry.items.map((item) =>
                "children" in item ? (
                  <SidebarMenuItem key={item.label}>
                    <SidebarMenuButton
                      className="group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:justify-center"
                      render={
                        <button
                          type="button"
                          aria-expanded={storesOpen}
                          onClick={() => setStoresOpen((open) => !open)}
                        >
                          <item.icon />
                          <span className="group-data-[collapsible=icon]:hidden">
                            {item.label}
                          </span>
                          <ChevronDown
                            className={cn(
                              "ms-auto transition-transform group-data-[collapsible=icon]:hidden",
                              storesOpen && "rotate-180"
                            )}
                          />
                        </button>
                      }
                      tooltip={item.label}
                      isActive={storesActive}
                    />
                    {storesOpen ? (
                      <SidebarMenuSub>
                        {item.children.map((child) => (
                          <SidebarMenuSubItem key={child.href}>
                            <SidebarMenuSubButton
                              render={
                                <Link
                                  href={child.href}
                                  onClick={closeMobileSidebar}
                                >
                                  <span>{child.label}</span>
                                </Link>
                              }
                              isActive={isLinkActive(child.href, pathname)}
                            />
                          </SidebarMenuSubItem>
                        ))}
                      </SidebarMenuSub>
                    ) : null}
                  </SidebarMenuItem>
                ) : item.soon ? (
                  <SidebarMenuItem key={item.href}>
                    <div className="relative">
                      <SidebarMenuButton
                        className="group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:justify-center"
                        render={
                          <span aria-disabled="true" className="opacity-60">
                            <item.icon />
                            <span className="group-data-[collapsible=icon]:hidden">
                              {item.label}
                            </span>
                          </span>
                        }
                        tooltip={`${item.label} — به‌زودی`}
                      />
                      <Badge
                        variant="secondary"
                        className="inset-e-2 absolute top-1/2 h-5 -translate-y-1/2 px-1.5 text-[10px] group-data-[collapsible=icon]:hidden"
                      >
                        به‌زودی
                      </Badge>
                    </div>
                  </SidebarMenuItem>
                ) : (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      className="group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:justify-center"
                      render={
                        <Link href={item.href} onClick={closeMobileSidebar}>
                          <item.icon />
                          <span className="group-data-[collapsible=icon]:hidden">
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

export function AppSidebarSkeleton() {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>منو</SidebarGroupLabel>
      <SidebarMenu>
        {Array.from({ length: 3 }).map((_, i) => (
          <SidebarMenuItem key={i}>
            <Skeleton className="h-8 w-full" />
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
