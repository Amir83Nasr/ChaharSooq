"use client"

import * as React from "react"
import { usePathname } from "next/navigation"

// Hex approximations of the surfaces in globals.css:
// page --background: light oklch(1 0 0), dark oklch(0.225 0.012 285).
const THEME_COLORS = { light: "#ffffff", dark: "#1b1b21" } as const

// Layout effect (not passive) so the browser navbar repaints in the same
// commit as the theme class flip — no one-frame two-tone flash on toggle.
const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? React.useLayoutEffect : React.useEffect

function currentThemeColor(): string {
  // next-themes applies the class synchronously in its blocking script, so
  // the DOM already knows the right theme on hydration. Never derive this
  // from useTheme().resolvedTheme: it is undefined for the first commit and
  // writing the light default at that point is the refresh-time navbar flash.
  return document.documentElement.classList.contains("dark")
    ? THEME_COLORS.dark
    : THEME_COLORS.light
}

function applyThemeColor() {
  const color = currentThemeColor()
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    // Guarded write: an unconditional setAttribute would re-trigger the
    // head observer below and loop.
    if (meta.getAttribute("content") !== color) {
      meta.setAttribute("content", color)
    }
  })
}

function ThemeColorSync() {
  const pathname = usePathname()

  useIsomorphicLayoutEffect(() => {
    applyThemeColor()
  }, [pathname])

  React.useEffect(() => {
    // Next rebuilds head metas around client-side navigation — possibly
    // after layout effects run — restoring the static fallback from the
    // viewport export and wiping our resolved-theme value. Re-assert after
    // paint, and keep observers so any later replacement (route head flush,
    // extension, theme toggle) gets corrected immediately.
    applyThemeColor()
    const headObserver = new MutationObserver(applyThemeColor)
    headObserver.observe(document.head, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["content", "media"],
    })
    // Theme changes update <html class> directly, outside React's render.
    const classObserver = new MutationObserver(applyThemeColor)
    classObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    })
    return () => {
      headObserver.disconnect()
      classObserver.disconnect()
    }
  }, [pathname])

  return null
}

export { ThemeColorSync }
