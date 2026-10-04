"use client"

import * as React from "react"
import { Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"

const OPTIONS = [
  { value: "light", label: "روشن", icon: Sun },
  { value: "dark", label: "تیره", icon: Moon },
  { value: "system", label: "سیستم", icon: Monitor },
] as const

export function ThemeSettings() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className="grid grid-cols-3 gap-2" dir="rtl">
        {OPTIONS.map((opt) => (
          <div
            key={opt.value}
            className="h-10 animate-pulse rounded-md bg-muted"
          />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="تم">
      {OPTIONS.map((opt) => {
        const active = theme === opt.value
        return (
          <Button
            key={opt.value}
            variant={active ? "default" : "outline"}
            role="radio"
            aria-checked={active}
            onClick={() => setTheme(opt.value)}
            className={cn("h-10")}
          >
            <opt.icon />
            <span>{opt.label}</span>
          </Button>
        )
      })}
    </div>
  )
}
