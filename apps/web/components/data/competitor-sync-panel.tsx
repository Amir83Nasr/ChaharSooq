"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { PersianDateTime } from "@workspace/ui/persian/persian-date"
import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { toPersianDigits } from "@workspace/ui/lib/number"
import { formatPersianRelativeTime } from "@workspace/ui/lib/relative-time"
import { api, ApiRequestError, type CompetitorSyncStatus } from "@/lib/api"

/** Poll while a run is active (fast) and when idle (catches completion). */
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
function lastRunFailed(status: CompetitorSyncStatus): boolean {
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

export function CompetitorSyncPanel({ onSynced, onUnauthorized }: Props) {
  const [status, setStatus] = useState<CompetitorSyncStatus | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // True after the first status round-trip settles (success or failure), so a
  // failed first fetch still re-enables the manual button instead of locking
  // it in a loading state.
  const [primed, setPrimed] = useState(false)
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
      if (cancelled) return
      if (pollingRef.current) {
        schedule()
        return
      }
      pollingRef.current = true
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const data = await api.competitorStatusSignal(controller.signal)
        if (cancelled) return
        pollsRef.current = data.running ? pollsRef.current + 1 : 0
        delay = data.running ? RUNNING_POLL_MS : IDLE_POLL_MS
        setStatus(data)
        // Re-fetch the catalog whenever a run finishes (success or failure)
        // so bulk price updates land without a full page reload.
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
        if (!cancelled) setPrimed(true)
        if (pollsRef.current > MAX_RUNNING_POLLS) {
          pollsRef.current = 0
          delay = IDLE_POLL_MS
          if (!cancelled) {
            setError(
              "به‌روزرسانی بیش از حد طول کشیده است؛ بعداً وضعیت را بررسی کنید."
            )
          }
        }
        schedule()
      }
    }

    void tick()
    return () => {
      cancelled = true
      pollingRef.current = false
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
      await api.competitorSync()
      // 409 = another run already owns the lock; the poller already shows
      // it as running, nothing extra to start.
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
  // The button stays disabled with a spinning icon until the first status
  // round-trip completes, so it reads as loading instead of active-but-stale.
  const loading = status === null && !primed
  const running = triggering || status?.running === true
  // Unified button animation: spinning icon during the initial load and while
  // a run is active — identical in both sync panels.
  const busy = !primed || running
  const disabled = !primed || running
  const failed = status !== null && !running && lastRunFailed(status)

  return (
    // Labeled buttons on every breakpoint (same look as all other buttons:
    // h-11 touch target on mobile, h-9 on sm+, unified rounded-2xl). The two
    // panels stack full-width on mobile so the Persian labels never clip.
    <div className="flex w-full flex-col gap-2 sm:w-56 sm:shrink-0">
      <Button
        onClick={runSync}
        disabled={disabled}
        aria-busy={busy}
        variant="outline"
        className="h-11 w-full justify-center gap-2 rounded-2xl sm:h-9"
      >
        <RefreshCw
          data-icon="inline-start"
          className={busy ? "size-4 shrink-0 animate-spin" : "size-4 shrink-0"}
          aria-hidden="true"
        />
        <span>به‌روزرسانی قیمت رقبا</span>
      </Button>
      {/* Two-line reserve: short/long status states swap without moving
          the content below. leading-4 locks the math (2 × 16px = min-h-8). */}
      <div
        className="hidden min-h-8 w-full text-start text-xs leading-4 text-muted-foreground sm:block"
        aria-live="polite"
      >
        {loading ? (
          <span className="inline-flex h-4 items-center">
            <span
              aria-hidden="true"
              className="inline-block h-3 w-40 animate-pulse rounded bg-muted"
            />
            <span className="sr-only">در حال بارگذاری وضعیت…</span>
          </span>
        ) : running ? (
          <span>به‌روزرسانی قیمت رقبا در حال اجراست</span>
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
          <span>هنوز قیمت رقبا به‌روزرسانی نشده است.</span>
        )}
      </div>
      {error ? (
        <p role="alert" className="w-full text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
