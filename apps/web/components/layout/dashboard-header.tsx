import { Separator } from "@workspace/ui/primitives/separator"
import { SidebarTrigger } from "@workspace/ui/primitives/sidebar"

import { ThemeToggle } from "@/components/layout/theme-toggle"
import { HeaderDateTime } from "@/components/layout/header-datetime"
import { DashboardBreadcrumbs } from "@/components/layout/dashboard-breadcrumbs"
import { MobileMenuButton } from "@/components/layout/mobile-menu-button"

export function DashboardHeader() {
  // Server shell: only the breadcrumbs re-render on navigation.
  // ThemeToggle and HeaderDateTime are isolated client islands, so the
  // per-second clock tick never re-renders the header or breadcrumbs.

  // Mobile is ChatGPT-like: no bar at all — an absolute overlay with a
  // top fade (bg-linear) so scrolled content melts away under it, carrying
  // only the floating menu button. pointer-events-none lets taps pass
  // through to the content below; the button re-enables them for itself.
  // The page title lives in each page's own PageHeader, and the theme is
  // set in Settings, so the mobile header carries nothing else. The sticky
  // mobile filter bars sit at top-14, exactly below this 56px zone, so the
  // two never overlap.
  // Desktop keeps the glass bar (kept by design): translucent bg +
  // backdrop blur over the grid layer. PERF: isolate pins the blur to
  // this stacking context so a theme flip or sidebar slide doesn't
  // re-rasterize sibling layers, and backdrop-blur-md keeps the glass
  // look at a cheaper blur radius than lg.
  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-30 flex h-14 shrink-0 items-center gap-2 bg-linear-to-b from-background via-background/60 to-transparent md:pointer-events-auto md:sticky md:isolate md:h-16 md:rounded-t-2xl md:border-b md:bg-background/50 md:bg-none md:backdrop-blur-md md:supports-[backdrop-filter]:bg-background/40">
      <div className="flex min-w-0 flex-1 items-center gap-2 px-3 sm:px-4">
        <MobileMenuButton />
        <div className="hidden min-w-0 flex-1 items-center gap-2 overflow-hidden md:flex">
          <SidebarTrigger className="-ms-1 shrink-0" />
          <span className="me-2 flex shrink-0 items-center">
            <Separator orientation="vertical" className="h-4" />
          </span>
          <DashboardBreadcrumbs />
        </div>
      </div>
      <div className="hidden shrink-0 items-center gap-1.5 px-3 sm:gap-2 sm:px-4 md:flex">
        <ThemeToggle />
        <div className="hidden sm:block">
          <HeaderDateTime />
        </div>
      </div>
    </header>
  )
}
