import { cookies } from "next/headers"
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
  // Respect the persisted sidebar state so a reload doesn't snap the
  // layout back to expanded. The layout is already dynamic (auth check
  // above reads cookies), so this adds no prerendering cost.
  const sidebarState = (await cookies()).get("sidebar_state")?.value
  const defaultOpen = sidebarState !== "false"
  return (
    <SidebarProvider
      defaultOpen={defaultOpen}
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
            container instead of pushing the whole page sideways.
            PERF: the square pattern lives on a dedicated non-scrolling
            layer below (same visuals), never as a background of the
            animating inset or the scroll container — that repainted the
            grid on every sidebar/scroll frame. */}
        <SidebarInset className="h-dvh min-w-0 overflow-hidden border border-border md:h-[calc(100dvh-1rem)]">
          {/* Static grid layer: absolute + non-scrolling, so sidebar slides
              move a cached texture and list scrolling never repaints it. */}
          <div
            aria-hidden="true"
            className="bg-grid-pattern pointer-events-none absolute inset-0 rounded-[inherit]"
          />
          <DashboardHeader />
          {/* Pull content under the header so the glass blur stays visible.
              data-slot="dashboard-scroll" marks the vertical scroll root for
              windowed tables (see use-windowed-rows). */}
          <div
            data-slot="dashboard-scroll"
            className="relative -mt-16 no-scrollbar flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-x-clip overflow-y-auto p-4 pt-20"
          >
            {children}
          </div>
        </SidebarInset>
      </LogoutProvider>
    </SidebarProvider>
  )
}
