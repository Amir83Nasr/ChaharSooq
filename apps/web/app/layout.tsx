import type { Metadata, Viewport } from "next"

import "@workspace/ui/globals.css"
import { ThemeColorSync } from "@/components/theme-color-sync"
import { ThemeProvider } from "@/components/theme-provider"
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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
}

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
        <ThemeProvider>
          <ThemeColorSync />
          <div id="charsooq-root" className="relative min-h-dvh">
            {/* Full-page fixed square pattern — stays put while content scrolls */}
            <div
              aria-hidden="true"
              className="bg-grid-pattern pointer-events-none fixed inset-0 -z-10"
            />
            {children}
          </div>
        </ThemeProvider>
      </body>
    </html>
  )
}
