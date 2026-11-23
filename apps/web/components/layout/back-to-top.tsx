"use client"

import { useEffect, useState } from "react"
import { ArrowUp } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"

// The dashboard never scrolls the window: the scroll root is the inset div
// marked in (dashboard)/layout.tsx. Match the same selector used by the
// windowed table hook so this button follows the real scroll position.
const SCROLL_ROOT_SELECTOR = '[data-slot="dashboard-scroll"]'
const SHOW_AFTER_PX = 320

export function BackToTop() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const container = document.querySelector<HTMLElement>(SCROLL_ROOT_SELECTOR)
    if (!container) return

    const onScroll = () => setVisible(container.scrollTop > SHOW_AFTER_PX)
    onScroll()
    container.addEventListener("scroll", onScroll, { passive: true })
    return () => container.removeEventListener("scroll", onScroll)
  }, [])

  function scrollToTop() {
    const container = document.querySelector<HTMLElement>(SCROLL_ROOT_SELECTOR)
    container?.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <Button
      variant="secondary"
      size="lg"
      aria-label="بازگشت به بالا"
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
      onClick={scrollToTop}
      className={`inset-e-4 fixed bottom-5 z-40 h-11 gap-2 rounded-full border-border/60 bg-secondary/70 px-3 shadow-md hover:bg-secondary/95 hover:shadow-lg md:px-4 ${
        visible ? "" : "hidden"
      }`}
    >
      <ArrowUp className="size-5" aria-hidden="true" />
      <span className="hidden text-sm md:inline">بازگشت به بالا</span>
    </Button>
  )
}
