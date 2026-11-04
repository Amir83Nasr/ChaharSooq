"use client"

import { useEffect, useState, type ReactNode } from "react"

import { PersianDateTime } from "@workspace/ui/persian/persian-date"
import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { formatPersianRelativeTime } from "@workspace/ui/lib/relative-time"
import { cn } from "@workspace/ui/lib/utils"

import type { CompetitorSyncStatus, SyncStatus } from "@/lib/api"

/** The last attempt failed when it recorded an error after the last success. */
function lastRunFailed(status: {
  last_error: string | null
  last_success_at: string | null
  last_attempt_at: string | null
}): boolean {
  if (!status.last_error) return false
  if (!status.last_success_at) return true
  if (!status.last_attempt_at) return false
  return (
    Date.parse(status.last_attempt_at) >= Date.parse(status.last_success_at)
  )
}

function SyncMoment({ value, now }: { value: string; now: number }) {
  const relative = formatPersianRelativeTime(value, now)
  if (relative === null) return <PersianDateTime value={value} />
  return <span title={formatPersianDateTime(value)}>{relative}</span>
}

function SyncDot({ tone }: { tone: "ok" | "bad" | "idle" }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-2 shrink-0 rounded-full",
        tone === "ok" && "bg-emerald-500",
        tone === "bad" && "bg-rose-500",
        tone === "idle" && "bg-muted-foreground/40"
      )}
    />
  )
}

type SyncStripProps = {
  parsina: SyncStatus | null
  competitor: CompetitorSyncStatus | null
}

export function SyncStrip({ parsina, competitor }: SyncStripProps) {
  // Refreshes relative timestamps ("۵ دقیقه پیش") without a status fetch.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])
  if (parsina === null && competitor === null) return null
  const items: ReactNode[] = []
  if (parsina !== null) {
    const tone = parsina.running
      ? "idle"
      : lastRunFailed(parsina)
        ? "bad"
        : parsina.last_success_at
          ? "ok"
          : "idle"
    items.push(
      <span key="parsina" className="inline-flex items-center gap-1.5">
        <SyncDot tone={tone} />
        <span className={cn(parsina.running && "animate-pulse")}>
          پارسینا:{" "}
          {parsina.running ? (
            "در حال اجرا…"
          ) : parsina.last_success_at ? (
            <SyncMoment value={parsina.last_success_at} now={now} />
          ) : (
            "هنوز انجام نشده"
          )}
        </span>
      </span>
    )
  }
  if (competitor !== null) {
    const tone = competitor.running
      ? "idle"
      : lastRunFailed(competitor)
        ? "bad"
        : competitor.last_success_at
          ? "ok"
          : "idle"
    items.push(
      <span key="competitor" className="inline-flex items-center gap-1.5">
        <SyncDot tone={tone} />
        <span className={cn(competitor.running && "animate-pulse")}>
          رقبا:{" "}
          {competitor.running ? (
            "در حال اجرا…"
          ) : competitor.last_success_at ? (
            <SyncMoment value={competitor.last_success_at} now={now} />
          ) : (
            "هنوز انجام نشده"
          )}
        </span>
      </span>
    )
  }
  return (
    <div
      aria-live="polite"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground"
    >
      {items}
    </div>
  )
}
