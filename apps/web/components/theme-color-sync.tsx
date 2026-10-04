"use client"

import * as React from "react"
import { useTheme } from "next-themes"

// Hex approximations of --background (oklch) in globals.css:
// light oklch(1 0 0), dark oklch(0.145 0 0).
const THEME_COLORS = { light: "#ffffff", dark: "#0a0a0a" } as const

function ThemeColorSync() {
  const { resolvedTheme } = useTheme()

  React.useEffect(() => {
    const color =
      resolvedTheme === "dark" ? THEME_COLORS.dark : THEME_COLORS.light
    document
      .querySelectorAll('meta[name="theme-color"]')
      .forEach((meta) => meta.setAttribute("content", color))
  }, [resolvedTheme])

  return null
}

export { ThemeColorSync }
