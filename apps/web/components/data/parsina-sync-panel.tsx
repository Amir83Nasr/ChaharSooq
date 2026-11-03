"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { PersianDateTime } from "@workspace/ui/persian/persian-date"
import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { toPersianDigits } from "@workspace/ui/lib/number"
import { formatPersianRelativeTime } from "@workspace/ui/lib/relative-time"
import { api, ApiRequestError, type SyncStatus } from "@/lib/api"

/** Poll while a run is active (fast) and when idle (catches the 15-min job). */
const RUNNING_POLL_MS = 2_000
const IDLE_POLL_MS = 45_000
/** A run whose lock never clears must not poll forever. */
const MAX_RUNNING_POLLS = 600

interface Props {
  /** Bumped once per new successful sync — table re-fetches in place. */
  onSynced: () => void
  onUnauthorized: () => void
}

/** The last attempt failed when it recorded an error after the last success. */
function lastRunFailed(status: SyncStatus): boolean {
  if (!status.last_error) return false
  if (!status.last_success_at) return true
  if (!status.last_attempt_at) return false
  return (
    Date.parse(status.last_attempt_at) >= Date.parse(status.last_success_at)
  )
}

/** Relative moment with the exact time as a hover tooltip. */
function RelativeMoment({ value, now }: { value: string; now: number }) {
  const relative = formatPersianRelativeTime(value, now)
  if (relative === null) return <PersianDateTime value={value} />
  return <span title={formatPersianDateTime(value)}>{relative}</span>
}

export function ParsinaSyncPanel({ onSynced, onUnauthorized }: Props) {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped after every manual press so the poll loop restarts at once and
  // the running state shows without waiting for the next idle tick.
  const [pollBump, setPollBump] = useState(0)
  // Refreshes relative timestamps ("۵ دقیقه پیش") without a status fetch.
  const [now, setNow] = useState(() => Date.now())

  const lastSuccess = useRef<string | null>(null)
  const triggeringRef = useRef(false)
  const pollingRef = useRef(false)
  const pollsRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const onSyncedRef = useRef(onSynced)
  const onUnauthorizedRef = useRef(onUnauthorized)
  onSyncedRef.current = onSynced
  onUnauthorizedRef.current = onUnauthorized

  const handle = useCallback((err: unknown) => {
    if (err instanceof ApiRequestError && err.status === 401) {
      onUnauthorizedRef.current()
      return
    }
    setError(err instanceof Error ? err.message : "خطایی رخ داد.")
  }, [])

  // Poll loop: one request in flight at a time, sequential timeouts (no
  // overlap), aborted on unmount. Transient errors just schedule the next tick.
  // A manual press restarts the loop via `pollBump` for instant feedback.
  useEffect(() => {
    const ticker = setInterval(() => setNow(Date.now()), 30_000)
    let cancelled = false
    let delay = IDLE_POLL_MS

    const schedule = () => {
      if (!cancelled) timerRef.current = setTimeout(tick, delay)
    }

    const tick = async () => {
      if (cancelled || pollingRef.current) return
      pollingRef.current = true
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const data = await api.parsinaStatusSignal(controller.signal)
        if (cancelled) return
        pollsRef.current = data.running ? pollsRef.current + 1 : 0
        delay = data.running ? RUNNING_POLL_MS : IDLE_POLL_MS
        setStatus(data)
        // Re-fetch the catalog whenever a run finishes (success or failure) so
        // manual and scheduled updates land without a full page reload.
        if (
          lastSuccess.current !== null &&
          data.last_success_at !== lastSuccess.current
        ) {
          onSyncedRef.current()
        }
        lastSuccess.current = data.last_success_at
      } catch (err: unknown) {
        // Temporary network/status errors change nothing visible: keep the
        // table, the last-known run state, and just retry on the next tick.
        if (err instanceof ApiRequestError && err.status === 401) {
          onUnauthorizedRef.current()
        }
      } finally {
        pollingRef.current = false
        if (pollsRef.current > MAX_RUNNING_POLLS) {
          pollsRef.current = 0
          delay = IDLE_POLL_MS
          if (!cancelled) {
            setError(
              "همگام‌سازی بیش از حد طول کشیده است؛ بعداً وضعیت را بررسی کنید."
            )
          }
        }
        schedule()
      }
    }

    void tick()
    return () => {
      cancelled = true
      clearInterval(ticker)
      if (timerRef.current) clearTimeout(timerRef.current)
      abortRef.current?.abort()
    }
  }, [pollBump])

  async function runSync() {
    // Synchronous guard runs before any await, so double clicks are inert.
    if (triggeringRef.current) return
    triggeringRef.current = true
    setTriggering(true)
    setError(null)
    try {
      await api.parsinaSync()
      // 409 = another run (manual or scheduled) owns the lock; the poller
      // already shows it as running, nothing extra to start.
    } catch (err: unknown) {
      if (err instanceof ApiRequestError && err.status === 409) {
        // Another run is already in progress; no extra text needed — the
        // status line already reflects the running state.
      } else {
        handle(err)
      }
    } finally {
      triggeringRef.current = false
      setTriggering(false)
      // Restart the poll loop at once: the running state (and, moments
      // later, the new success timestamp) shows without idle delay.
      setPollBump((b) => b + 1)
    }
  }

  // While a run is active the backend owns the state: on the next poll the
  // completion is detected through `last_success_at` and the table refreshes.
  const running = triggering || status?.running === true
  const notConfigured = status !== null && !status.configured
  const disabled = running || notConfigured
  const failed =
    status !== null && !running && !notConfigured && lastRunFailed(status)

  return (
    // Full-width rows on mobile with the button pinned to the row's start
    // edge: the status line underneath can change length without pushing
    // the button around. On sm+ the panel shrinks to its content at the
    // header's end edge, where `sm:items-end` keeps the same pinning.
    <div className="flex w-full flex-col items-start gap-2 sm:w-auto sm:items-end">
      <Button onClick={runSync} disabled={disabled} aria-busy={running}>
        <RefreshCw
          className={running ? "animate-spin" : undefined}
          aria-hidden="true"
        />
        {/* Stable width in both states: the sizer (always the longer label)
            reserves the width in normal flow while the overlay shows the
            active label centered. The sizer uses transparent paint instead of
            `visibility: hidden` — fully laid out in every engine — plus
            `aria-hidden` and non-selectable text so it stays out of the way. */}
        <span style={{ position: "relative", display: "inline-block" }}>
          <span
            aria-hidden="true"
            style={{
              color: "transparent",
              userSelect: "none",
              whiteSpace: "nowrap",
            }}
          >
            در حال به‌روزرسانی…
          </span>
          <span
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              whiteSpace: "nowrap",
            }}
          >
            {running ? "در حال به‌روزرسانی…" : "به‌روزرسانی اطلاعات"}
          </span>
        </span>
      </Button>
      <div
        className="w-full text-start text-xs text-muted-foreground"
        aria-live="polite"
      >
        {notConfigured ? (
          <span>
            {status?.source === "csv"
              ? "فایل داده آزمایشی محصولات یافت نشد."
              : status?.source === "dev"
                ? "اتصال دیتابیس dev تنظیم نشده است."
                : "اتصال پارسینا تنظیم نشده است."}
          </span>
        ) : running ? (
          <span>
            همگام‌سازی در حال اجراست
            {status?.running_since ? (
              <>
                {" — آغاز "}
                <PersianDateTime value={status.running_since} />
              </>
            ) : null}
          </span>
        ) : failed && status?.last_error ? (
          <span className="text-destructive">
            آخرین تلاش ناموفق بود
            {status.last_attempt_at ? (
              <>
                {" — "}
                <RelativeMoment value={status.last_attempt_at} now={now} />
              </>
            ) : null}
            {": "}
            {toPersianDigits(status.last_error)}
          </span>
        ) : status?.last_success_at ? (
          <span>
            آخرین به‌روزرسانی موفق:{" "}
            <RelativeMoment value={status.last_success_at} now={now} />
          </span>
        ) : (
          <span>هنوز به‌روزرسانی موفقی انجام نشده است.</span>
        )}
      </div>
      {error ? (
        <p role="alert" className="max-w-sm text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
