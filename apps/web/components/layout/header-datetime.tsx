"use client"

import { useEffect, useState } from "react"
import { CalendarDays, Clock } from "lucide-react"

import {
  formatPersianDate,
  formatPersianTime,
  formatPersianWeekday,
} from "@workspace/ui/lib/date"

export function HeaderDateTime() {
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    setNow(new Date())
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  if (!now) {
    return (
      <span
        aria-hidden="true"
        className="h-8 w-56 animate-pulse rounded-md bg-muted"
      />
    )
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground shadow-xs">
        <time
          dateTime={now.toISOString()}
          className="inline-block min-w-[9ch] text-center leading-none tabular-nums"
        >
          {formatPersianTime(now, true)}
        </time>
        <Clock
          className="size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
      </div>
      <div className="flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground shadow-xs">
        <time dateTime={now.toISOString()} className="leading-none">
          {formatPersianWeekday(now)} {formatPersianDate(now)}
        </time>
        <CalendarDays
          className="size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    </div>
  )
}
