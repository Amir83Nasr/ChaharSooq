"use client"

import { useEffect, useState } from "react"
import { CalendarDays, Clock } from "lucide-react"

import {
  formatPersianDate,
  formatPersianTime,
  formatPersianWeekday,
} from "@workspace/ui/lib/date"

function useNow(intervalMs: number, alignToSecond: boolean) {
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    let id: ReturnType<typeof setTimeout>
    let cancelled = false

    const tick = () => {
      if (cancelled) return
      setNow(new Date())
      const delay = alignToSecond ? 1000 - (Date.now() % 1000) : intervalMs
      id = setTimeout(tick, delay)
    }

    // Align the first tick to the wall-clock second so the displayed
    // time doesn't drift behind by up to a second after reload.
    const initialDelay = alignToSecond ? 1000 - (Date.now() % 1000) : intervalMs
    setNow(new Date())
    id = setTimeout(tick, initialDelay)

    return () => {
      cancelled = true
      clearTimeout(id)
    }
  }, [intervalMs, alignToSecond])

  return now
}

function TimePillSkeleton() {
  return (
    <div className="flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5">
      <span
        aria-hidden="true"
        className="inline-block h-4 min-w-[9ch] animate-pulse rounded-sm bg-muted"
      />
      <Clock
        className="size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
    </div>
  )
}

function DatePillSkeleton() {
  return (
    <div className="flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5">
      <span
        aria-hidden="true"
        className="inline-block h-4 w-28 animate-pulse rounded-sm bg-muted"
      />
      <CalendarDays
        className="size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
    </div>
  )
}

function HeaderClock() {
  const now = useNow(1000, true)

  if (!now) return <TimePillSkeleton />

  return (
    <div className="flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground shadow-xs">
      <time
        dateTime={now.toISOString()}
        suppressHydrationWarning
        className="inline-block min-w-[9ch] text-center leading-none tabular-nums"
      >
        {formatPersianTime(now, true)}
      </time>
      <Clock
        className="size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
    </div>
  )
}

function HeaderDate() {
  // The Jalali date only changes at midnight, so re-rendering once a
  // minute is plenty — the per-second clock tick must not touch this.
  const now = useNow(60_000, false)

  if (!now) return <DatePillSkeleton />

  return (
    <div className="flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground shadow-xs">
      <time dateTime={now.toISOString()} className="leading-none">
        {formatPersianWeekday(now)} {formatPersianDate(now)}
      </time>
      <CalendarDays
        className="size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
    </div>
  )
}

export function HeaderDateTime() {
  return (
    <div className="flex items-center gap-2">
      <HeaderClock />
      <HeaderDate />
    </div>
  )
}
