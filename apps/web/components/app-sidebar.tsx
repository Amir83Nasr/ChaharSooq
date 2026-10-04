"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BarChart3,
  Boxes,
  Calculator,
  LayoutDashboard,
  Package,
  Scale,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Tag,
  Truck,
  Users,
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
} from "@workspace/ui/components/sidebar"
import { Badge } from "@workspace/ui/components/badge"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { LogoutMenuItem } from "@/components/logout-menu-item"

const NAV = [
  {
    group: "داشبورد",
    items: [{ href: "/dashboard", label: "داشبورد", icon: LayoutDashboard }],
  },
  {
    group: "فروش",
    items: [
      { href: "/orders", label: "سفارش‌ها", icon: ShoppingCart, soon: true },
      { href: "/customers", label: "مشتریان", icon: Users, soon: true },
      { href: "/discounts", label: "تخفیف‌ها", icon: Tag, soon: true },
    ],
  },
  {
    group: "مدیریت",
    items: [
      { href: "/products", label: "محصولات", icon: Package },
      { href: "/inventory", label: "موجودی انبار", icon: Boxes, soon: true },
      { href: "/suppliers", label: "تأمین‌کنندگان", icon: Truck, soon: true },
    ],
  },
  {
    group: "گزارش‌ها",
    items: [{ href: "/reports", label: "گزارش فروش", icon: BarChart3, soon: true }],
  },
  // ponytail: لینک‌نما با soon؛ صفحه/ API واقعی هنگام اتصال ترب و سپیدار.
  {
    group: "یکپارچه‌سازی",
    items: [
      { href: "/integrations/torob", label: "اتصال ترب", icon: Scale, soon: true },
      { href: "/integrations/sepidar", label: "اتصال سپیدار", icon: Calculator, soon: true },
    ],
  },
  {
    group: "سیستم",
    items: [
      { href: "/users", label: "کاربران", icon: ShieldCheck, soon: true },
      { href: "/settings", label: "تنظیمات", icon: Settings },
    ],
  },
] as const

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon" side="right" {...props}>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground">
            چ
          </span>
          <span className="flex min-w-0 flex-col">
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
              {entry.items.map((item) => (
                <SidebarMenuItem key={item.href}>
                  {"soon" in item && item.soon ? (
                    <div className="relative">
                      <SidebarMenuButton
                        render={
                          <span aria-disabled="true" className="opacity-60">
                            <item.icon />
                            <span>{item.label}</span>
                          </span>
                        }
                        tooltip={`${item.label} — به‌زودی`}
                      />
                      <Badge
                        variant="secondary"
                        className="absolute inset-e-2 top-1/2 h-5 -translate-y-1/2 px-1.5 text-[10px] group-data-[collapsible=icon]:hidden"
                      >
                        به‌زودی
                      </Badge>
                    </div>
                  ) : (
                    <SidebarMenuButton
                      render={
                        <Link href={item.href}>
                          <item.icon />
                          <span>{item.label}</span>
                        </Link>
                      }
                      tooltip={item.label}
                      isActive={
                        item.href === "/dashboard"
                          ? pathname === item.href
                          : pathname === item.href ||
                            pathname.startsWith(item.href + "/")
                      }
                    />
                  )}
                </SidebarMenuItem>
              ))}
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
