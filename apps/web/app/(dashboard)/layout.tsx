import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@workspace/ui/components/sidebar"

import { AppSidebar } from "@/components/app-sidebar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Desktop sidebar is locked open (no collapse); mobile still uses the drawer.
  return (
    <SidebarProvider open>
      <AppSidebar />
      <SidebarInset>
        <header className="flex items-center gap-2 border-b border-border px-4 py-2 md:hidden">
          <SidebarTrigger />
          <span className="text-sm font-bold">چهارسوق</span>
        </header>
        <div className="flex min-w-0 flex-1 flex-col gap-6 p-4 md:p-6">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
