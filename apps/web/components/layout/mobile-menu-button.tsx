"use client"

import { Menu } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { useSidebar } from "@workspace/ui/primitives/sidebar"

export function MobileMenuButton() {
  const { toggleSidebar } = useSidebar()
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleSidebar}
      aria-label="باز کردن منو"
      className="pointer-events-auto size-11 shrink-0 rounded-2xl border border-border/60 bg-background/80 shadow-sm backdrop-blur-md md:hidden"
    >
      <Menu className="size-5" aria-hidden="true" />
      <span className="sr-only">باز کردن منو</span>
    </Button>
  )
}
