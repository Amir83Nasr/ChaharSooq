"use client"

import { useEffect, useState } from "react"
import { Database, Store } from "lucide-react"

import { Card, CardContent } from "@workspace/ui/primitives/card"
import { PersianDateTime } from "@workspace/ui/persian/persian-date"
import { formatPersianRelativeTime } from "@workspace/ui/lib/relative-time"
import { cn } from "@workspace/ui/lib/utils"

import type { CompetitorSyncStatus, SyncStatus } from "@/lib/api"

type Tone = "ok" | "bad" | "busy" | "idle"

type SyncState = {
  last_error: string | null
  last_success_at: string | null
  last_attempt_at: string | null
  running: boolean
}

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

function toneOf(status: SyncState): Tone {
  if (status.running) return "busy"
  if (lastRunFailed(status)) return "bad"
  if (status.last_success_at) return "ok"
  return "idle"
}

const PILL_LABEL: Record<Tone, string> = {
  ok: "به‌روز",
  bad: "خطا در آخرین اجرا",
  busy: "در حال اجرا",
  idle: "هنوز انجام نشده",
}

const PILL_CLASS: Record<Tone, string> = {
  ok: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-500",
  bad: "bg-rose-500/10 text-rose-600 dark:text-rose-500",
  busy: "bg-sky-500/10 text-sky-600 dark:text-sky-500",
  idle: "bg-muted text-muted-foreground",
}

function SyncTime({ value, now }: { value: string; now: number }) {
  const relative = formatPersianRelativeTime(value, now)
  return (
    <>
      <p className="text-xl font-bold">
        {relative ?? <PersianDateTime value={value} />}
      </p>
      {relative ? (
        <p className="text-xs text-muted-foreground">
          <PersianDateTime value={value} />
        </p>
      ) : null}
    </>
  )
}

function SyncCard({
  title,
  icon,
  tileClass,
  status,
  now,
}: {
  title: string
  icon: React.ReactNode
  tileClass: string
  status: SyncState
  now: number
}) {
  const tone = toneOf(status)
  return (
    <Card>
      <CardContent className="flex items-center gap-3 px-4 py-3.5 sm:gap-4 sm:px-5 sm:py-4">
        <span className="relative shrink-0">
          <span className={cn("block rounded-2xl p-3", tileClass)}>{icon}</span>
          {status.running ? (
            <span
              aria-hidden="true"
              className="absolute -end-1 -top-1 flex size-3"
            >
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
              <span className="relative inline-flex size-3 rounded-full bg-sky-500 ring-2 ring-background" />
            </span>
          ) : null}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold">{title}</p>
            <span
              className={cn(
                "ms-auto shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
                PILL_CLASS[tone],
                status.running && "animate-pulse"
              )}
            >
              {PILL_LABEL[tone]}
            </span>
          </div>
          {status.running ? (
            <p className="animate-pulse text-xl font-bold">
              در حال همگام‌سازی…
            </p>
          ) : tone === "ok" && status.last_success_at ? (
            <SyncTime value={status.last_success_at} now={now} />
          ) : status.last_attempt_at ? (
            <SyncTime value={status.last_attempt_at} now={now} />
          ) : (
            <p className="text-xl font-bold text-muted-foreground">—</p>
          )}
          {tone === "bad" && status.last_error ? (
            <p
              className="truncate text-xs text-rose-600 dark:text-rose-500"
              title={status.last_error}
            >
              {status.last_error}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

type SyncStatusCardsProps = {
  parsina: SyncStatus | null
  competitor: CompetitorSyncStatus | null
}

export function SyncStatusCards({ parsina, competitor }: SyncStatusCardsProps) {
  // Refreshes relative timestamps ("۵ دقیقه پیش") without a status fetch.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])
  if (parsina === null && competitor === null) return null
  return (
    <div aria-live="polite" className="grid gap-2.5 sm:gap-4 md:grid-cols-2">
      {parsina ? (
        <SyncCard
          title="پارسینا"
          icon={<Database className="size-5" aria-hidden="true" />}
          tileClass="bg-primary/10 text-primary"
          status={parsina}
          now={now}
        />
      ) : null}
      {competitor ? (
        <SyncCard
          title="رقبا"
          icon={<Store className="size-5" aria-hidden="true" />}
          tileClass="bg-sky-500/10 text-sky-600 dark:text-sky-500"
          status={competitor}
          now={now}
        />
      ) : null}
    </div>
  )
}
