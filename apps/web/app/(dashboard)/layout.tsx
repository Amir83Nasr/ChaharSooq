import { redirect } from "next/navigation"
import {
  SidebarInset,
  SidebarProvider,
} from "@workspace/ui/components/sidebar"

import { AppSidebar } from "@/components/app-sidebar"
import { DashboardHeader } from "@/components/dashboard-header"
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
      <AppSidebar variant="inset" />
      {/* min-w-0 lets the inset shrink below its content's min-content
          width, so wide inner scrollers (tables) scroll inside their own
          container instead of pushing the whole page sideways. */}
      <SidebarInset className="min-w-0">
        <DashboardHeader />
        <div className="flex min-w-0 flex-col gap-4 overflow-x-clip p-4">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  )
}
