import { redirect } from "next/navigation"
import {
  SidebarInset,
  SidebarProvider,
} from "@workspace/ui/components/sidebar"

import { AppSidebar } from "@/components/app-sidebar"
import { DashboardHeader } from "@/components/dashboard-header"
import { LogoutProvider } from "@/components/logout-menu-item"
import { getSessionAdmin } from "@/lib/auth"

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const admin = await getSessionAdmin()
  if (!admin) redirect("/login")
  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <LogoutProvider>
        <AppSidebar variant="inset" />
        {/* min-w-0 lets the inset shrink below its content's min-content
            width, so wide inner scrollers (tables) scroll inside their own
            container instead of pushing the whole page sideways. */}
        <SidebarInset className="h-dvh min-w-0 overflow-hidden md:h-[calc(100dvh-1rem)]">
          <DashboardHeader />
          <div className="no-scrollbar flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-x-clip overflow-y-auto p-4">
            {children}
          </div>
        </SidebarInset>
      </LogoutProvider>
    </SidebarProvider>
  )
}
