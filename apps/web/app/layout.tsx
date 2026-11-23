import type { Metadata, Viewport } from "next"

import "@workspace/ui/globals.css"
import { Toaster } from "@workspace/ui/primitives/sonner"
import { ThemeColorSync } from "@/components/layout/theme-color-sync"
import { ThemeProvider } from "@/components/layout/theme-provider"
import { cn } from "@workspace/ui/lib/utils"

import { iranYekanX } from "./fonts"

export const metadata: Metadata = {
  title: "چهارسوق | پنل مدیریت",
  description: "پنل مدیریت فروشگاه چهارسوق",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  // One meta only. Media-scoped metas make the browser pick a color from the
  // OS preference, which disagrees with an explicit in-app theme on refresh
  // and flashes the navbar from one color to the other. The inline script
  // below overwrites this fallback with the resolved theme before first paint.
  themeColor: "#ffffff",
}

// Mirrors next-themes' storage key/default (attribute="class", theme="system").
// Runs synchronously before paint so the browser navbar starts with the same
// color as the page instead of flipping once the provider hydrates.
const THEME_COLOR_BOOTSTRAP = `(() => {
  const dark = "#1b1b21";
  const light = "#ffffff";
  let theme;
  try { theme = localStorage.getItem("theme") || "system"; } catch {}
  const isDark = theme === "dark" || (theme === "system" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches);
  const color = isDark ? dark : light;
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.setAttribute("content", color);
  });
})();`

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="fa"
      dir="rtl"
      suppressHydrationWarning
      className={cn("antialiased", iranYekanX.variable, "font-sans")}
    >
      <body>
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: THEME_COLOR_BOOTSTRAP }}
        />
        <ThemeProvider>
          <ThemeColorSync />
          <div id="charsooq-root" className="relative min-h-dvh">
            {children}
          </div>
          <Toaster position="bottom-center" richColors closeButton />
        </ThemeProvider>
      </body>
    </html>
  )
}
