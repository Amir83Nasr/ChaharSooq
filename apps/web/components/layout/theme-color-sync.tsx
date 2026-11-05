"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"

// Hex approximations of the surfaces in globals.css:
// page --background: light oklch(1 0 0), dark oklch(0.225 0.012 285).
const THEME_COLORS = { light: "#ffffff", dark: "#1b1b21" } as const

// Layout effect (not passive) so the browser navbar repaints in the same
// commit as the theme class flip — no one-frame two-tone flash on toggle.
const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? React.useLayoutEffect : React.useEffect

function applyThemeColor(resolvedTheme: string | undefined) {
  const color =
    resolvedTheme === "dark" ? THEME_COLORS.dark : THEME_COLORS.light
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    // Guarded write: an unconditional setAttribute would re-trigger the
    // head observer below and loop.
    if (meta.getAttribute("content") !== color) {
      meta.setAttribute("content", color)
    }
  })
}

function ThemeColorSync() {
  const { resolvedTheme } = useTheme()
  const pathname = usePathname()

  useIsomorphicLayoutEffect(() => {
    applyThemeColor(resolvedTheme)
  }, [resolvedTheme, pathname])

  React.useEffect(() => {
    // Next rebuilds head metas around client-side navigation — possibly
    // after layout effects run — restoring the system-media values from
    // the viewport export and wiping our user-theme override. Re-assert
    // after paint, and keep a head observer so any later replacement
    // (route head flush, extension, etc.) gets corrected immediately.
    applyThemeColor(resolvedTheme)
    const observer = new MutationObserver(() => applyThemeColor(resolvedTheme))
    observer.observe(document.head, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["content", "media"],
    })
    return () => observer.disconnect()
  }, [resolvedTheme, pathname])

  return null
}

export { ThemeColorSync }
