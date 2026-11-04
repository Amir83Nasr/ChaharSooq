import { Separator } from "@workspace/ui/primitives/separator"
import { SidebarTrigger } from "@workspace/ui/primitives/sidebar"

import { ThemeToggle } from "@/components/layout/theme-toggle"
import { HeaderDateTime } from "@/components/layout/header-datetime"
import { DashboardBreadcrumbs } from "@/components/layout/dashboard-breadcrumbs"

export function DashboardHeader() {
  // Server shell: only DashboardBreadcrumbs re-renders on navigation.
  // ThemeToggle and HeaderDateTime are isolated client islands, so the
  // per-second clock tick never re-renders the header or breadcrumbs.

  // TEST-UI-1: glass header (revert to bg-background if laggy/bad).
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 overflow-hidden border-b bg-background/50 backdrop-blur-lg supports-[backdrop-filter]:bg-background/40 md:rounded-t-xl">
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden px-3 sm:px-4">
        <SidebarTrigger className="-ms-1 shrink-0" />
        <span className="me-2 hidden shrink-0 items-center min-[420px]:flex">
          <Separator orientation="vertical" className="h-4" />
        </span>
        <DashboardBreadcrumbs />
      </div>
      <div className="flex shrink-0 items-center gap-1.5 px-3 sm:gap-2 sm:px-4">
        <ThemeToggle />
        <div className="hidden sm:block">
          <HeaderDateTime />
        </div>
      </div>
    </header>
  )
}
