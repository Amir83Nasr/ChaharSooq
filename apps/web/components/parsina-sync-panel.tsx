"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { PersianDateTime } from "@workspace/ui/components/persian-date"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { api, ApiRequestError, type SyncStatus } from "@/lib/api"
import { syncSummaryMessage } from "@/lib/parsina"

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

export function ParsinaSyncPanel({ onSynced, onUnauthorized }: Props) {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  useEffect(() => {
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
        if (
          lastSuccess.current !== null &&
          data.last_success_at !== lastSuccess.current
        ) {
          setMessage(syncSummaryMessage(data))
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
      if (timerRef.current) clearTimeout(timerRef.current)
      abortRef.current?.abort()
    }
  }, [])

  async function runSync() {
    // Synchronous guard runs before any await, so double clicks are inert.
    if (triggeringRef.current) return
    triggeringRef.current = true
    setTriggering(true)
    setMessage(null)
    setError(null)
    try {
      const run = await api.parsinaSync()
      if (run.message) setMessage(run.message)
      // 409 = another run (manual or scheduled) owns the lock; the poller
      // already shows it as running, nothing extra to start.
    } catch (err: unknown) {
      if (err instanceof ApiRequestError && err.status === 409) {
        setMessage(err.message)
      } else {
        handle(err)
      }
    } finally {
      triggeringRef.current = false
      setTriggering(false)
    }
  }

  // While a run is active the backend owns the state: on the next poll the
  // completion is detected through `last_success_at` and the table refreshes.
  const running = triggering || status?.running === true
  const notConfigured = status !== null && !status.configured
  const disabled = running || notConfigured
  // Latest finished run failed (and nothing newer succeeded).
  const lastRunFailed =
    !!status?.last_error &&
    (!status.last_success_at ||
      status.last_attempt_at !== status.last_success_at)

  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-end">
      <Button onClick={runSync} disabled={disabled} aria-busy={running}>
        <RefreshCw
          className={running ? "animate-spin" : undefined}
          aria-hidden="true"
        />
        {running ? "در حال به‌روزرسانی…" : "به‌روزرسانی اطلاعات"}
      </Button>
      <div className="text-xs text-muted-foreground" aria-live="polite">
        {notConfigured ? (
          <span>
            {status?.source === "csv"
              ? "فایل داده آزمایشی محصولات یافت نشد."
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
        ) : status?.last_success_at ? (
          <span>
            آخرین به‌روزرسانی موفق:{" "}
            <PersianDateTime value={status.last_success_at} />
          </span>
        ) : (
          <span>هنوز به‌روزرسانی موفقی انجام نشده است.</span>
        )}
      </div>
      {status?.last_attempt_at &&
      status.last_attempt_at !== status.last_success_at ? (
        <p className="text-xs text-muted-foreground">
          آخرین تلاش: <PersianDateTime value={status.last_attempt_at} />
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="text-xs text-emerald-700 dark:text-emerald-300"
        >
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="max-w-sm text-xs text-destructive">
          {error}
        </p>
      ) : null}
      {lastRunFailed && !error ? (
        <p role="alert" className="max-w-sm text-xs text-destructive">
          آخرین به‌روزرسانی ناموفق بود: {status.last_error} — اطلاعات قبلی حفظ
          شده است.
        </p>
      ) : null}
      {status?.source === "csv" ? (
        <p className="text-xs text-muted-foreground">
          منبع داده: فایل CSV محیط توسعه
        </p>
      ) : null}
      {status?.last_success_at ? (
        <p className="text-xs text-muted-foreground">
          <PersianNumber value={status.last_processed} /> کالا در آخرین
          {status.source === "csv" ? " بارگذاری" : " همگام‌سازی"}
          {status.source === "csv" ? null : (
            <>
              {" · "}
              هر <PersianNumber value={status.interval_minutes} /> دقیقه
            </>
          )}
        </p>
      ) : null}
    </div>
  )
}
