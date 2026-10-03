"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  LayoutDashboard,
  Package,
  Settings,
  BarChart3,
  LogOut,
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
import { api } from "@/lib/api"

const NAV = [
  { href: "/dashboard", label: "داشبورد", icon: LayoutDashboard },
  {
    group: "مدیریت",
    items: [{ href: "/products", label: "محصولات", icon: Package }],
  },
  {
    group: "گزارش‌ها",
    items: [{ href: "/reports", label: "گزارش فروش", icon: BarChart3 }],
  },
  { href: "/settings", label: "تنظیمات", icon: Settings },
] as const

export function AppSidebar() {
  const pathname = usePathname()
  const router = useRouter()

  async function onLogout() {
    try {
      await api.logout()
    } finally {
      router.push("/login")
      router.refresh()
    }
  }

  return (
    <Sidebar variant="sidebar" collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground">
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
        {NAV.map((entry) =>
          "group" in entry ? (
            <SidebarGroup key={entry.group}>
              <SidebarGroupLabel>{entry.group}</SidebarGroupLabel>
              <SidebarMenu>
                {entry.items.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      render={
                        <Link href={item.href}>
                          <item.icon />
                          <span>{item.label}</span>
                        </Link>
                      }
                      isActive={pathname === item.href}
                    />
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroup>
          ) : (
            <SidebarGroup key={entry.href}>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    render={
                      <Link href={entry.href}>
                        <entry.icon />
                        <span>{entry.label}</span>
                      </Link>
                    }
                    isActive={pathname === entry.href}
                  />
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroup>
          )
        )}
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              render={<button type="button" onClick={onLogout} />}
            >
              <LogOut />
              <span>خروج</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
