"use client"

import * as React from "react"
import { useTheme } from "next-themes"

// Hex approximations of the dark surfaces in globals.css:
// page gutter --sidebar oklch(0.18 0.01 285), content --background oklch(0.225 0.012 285).
const THEME_COLORS = { light: "#ffffff", dark: "#131318" } as const

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
