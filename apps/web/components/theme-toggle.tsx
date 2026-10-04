"use client"

import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@workspace/ui/components/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="تغییر تم"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          >
            <Sun className="size-4 scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
            <Moon className="absolute size-4 scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
            <span className="sr-only">تغییر تم</span>
          </Button>
        }
      />
      <TooltipContent side="bottom" className="hidden md:inline-flex">
        تغییر تم
        <kbd
          data-slot="kbd"
          className="rounded bg-background/20 px-1 font-mono text-[10px] leading-4"
        >
          D
        </kbd>
      </TooltipContent>
    </Tooltip>
  )
}
