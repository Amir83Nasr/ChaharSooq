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

function isLinkActive(href: string, pathname: string) {
  return href === "/dashboard"
    ? pathname === href
    : pathname === href || pathname.startsWith(`${href}/`)
}

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()
  const { isMobile, setOpenMobile, state } = useSidebar()
  const storesActive = pathname.startsWith("/integrations")
  const [storesOpen, setStoresOpen] = useState(storesActive)
  // Links are keyboard-reachable only when the submenu is actually visible:
  // open, and (on desktop) the sidebar expanded. On mobile the sidebar is
  // a sheet, so the desktop collapsed state doesn't apply.
  const submenuAccessible = storesOpen && (isMobile || state === "expanded")

  useEffect(() => {
    if (storesActive) setStoresOpen(true)
  }, [storesActive])

  const closeMobileSidebar = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <Sidebar collapsible="offcanvas" side="right" {...props}>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-0 py-1 transition-[gap] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-data-[collapsible=icon]:gap-0 motion-reduce:transition-none">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground">
            چ
          </span>
          <span className="sidebar-collapse-label flex min-w-0 flex-col">
            <span className="text-sm font-bold">چهارسوق</span>
            <span className="text-xs text-muted-foreground">
              پنل مدیریت فروشگاه
            </span>
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {NAV.map((entry) => (
          <SidebarGroup key={entry.group}>
            <SidebarGroupLabel>{entry.group}</SidebarGroupLabel>
            <SidebarMenu>
              {entry.items.map((item) =>
                "children" in item ? (
                  <SidebarMenuItem key={item.label}>
                    <SidebarMenuButton
                      render={
                        <button
                          type="button"
                          aria-expanded={storesOpen}
                          onClick={() => setStoresOpen((open) => !open)}
                        >
                          <item.icon className="sidebar-collapse-icon" />
                          <span className="sidebar-collapse-label">
                            {item.label}
                          </span>
                          <ChevronDown
                            className={cn(
                              "sidebar-collapse-fade ms-auto",
                              storesOpen && "rotate-180"
                            )}
                          />
                        </button>
                      }
                      tooltip={item.label}
                      isActive={storesActive}
                    />
                    <div
                      className="sidebar-submenu-grid"
                      data-open={storesOpen}
                      aria-hidden={!submenuAccessible}
                    >
                      <div>
                        <SidebarMenuSub aria-hidden={!submenuAccessible}>
                          {item.children.map((child) => (
                            <SidebarMenuSubItem
                              key={child.href}
                              aria-hidden={!submenuAccessible}
                            >
                              <SidebarMenuSubButton
                                render={
                                  <Link
                                    href={child.href}
                                    onClick={closeMobileSidebar}
                                    tabIndex={
                                      submenuAccessible ? undefined : -1
                                    }
                                  >
                                    <span>{child.label}</span>
                                  </Link>
                                }
                                isActive={isLinkActive(child.href, pathname)}
                              />
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </div>
                    </div>
                  </SidebarMenuItem>
                ) : item.soon ? (
                  <SidebarMenuItem key={item.href} aria-hidden={false}>
                    <div className="relative">
                      <SidebarMenuButton
                        render={
                          <span
                            aria-disabled="true"
                            tabIndex={-1}
                            aria-label={`${item.label} — به‌زودی`}
                            className="opacity-60"
                          >
                            <item.icon className="sidebar-collapse-icon" />
                            <span className="sidebar-collapse-label">
                              {item.label}
                            </span>
                          </span>
                        }
                        tooltip={`${item.label} — به‌زودی`}
                      />
                      <Badge
                        variant="secondary"
                        className="sidebar-collapse-fade inset-e-2 absolute top-1/2 h-5 -translate-y-1/2 px-1.5 text-[10px]"
                      >
                        به‌زودی
                      </Badge>
                    </div>
                  </SidebarMenuItem>
                ) : (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      render={
                        <Link href={item.href} onClick={closeMobileSidebar}>
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
