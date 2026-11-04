import { redirect } from "next/navigation"
import { SidebarInset, SidebarProvider } from "@workspace/ui/primitives/sidebar"

import { AppSidebar } from "@/components/layout/app-sidebar"
import { DashboardHeader } from "@/components/layout/dashboard-header"
import { LogoutProvider } from "@/components/auth/logout-menu-item"
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
        <SidebarInset className="bg-grid-pattern h-dvh min-w-0 overflow-hidden border border-border md:h-[calc(100dvh-1rem)]">
          <DashboardHeader />
          {/* TEST-UI-1b: pull content under header so glass blur is visible */}
          <div className="-mt-16 no-scrollbar flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-x-clip overflow-y-auto p-4 pt-20">
            {children}
          </div>
        </SidebarInset>
      </LogoutProvider>
    </SidebarProvider>
  )
}
