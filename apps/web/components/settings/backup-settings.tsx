"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import {
  formatPersianNumber,
  toLatinDigits,
  toPersianDigits,
} from "@workspace/ui/lib/number"

import { api, type BackupSettings } from "@/lib/api"

const MINUTES_PER_DAY = 1440
const MIN_DAYS = 1
const MAX_DAYS = 7

function minutesToDays(minutes: number): string {
  // Stored settings may predate the day-based UI; show a whole day at minimum.
  return String(Math.max(MIN_DAYS, Math.ceil(minutes / MINUTES_PER_DAY)))
}

function parseDaysInput(value: string): string {
  return toLatinDigits(value)
    .replace(/[^0-9]/g, "")
    .slice(0, 2)
}

/** Owner-only automatic backup toggle and interval editor. */
export function BackupSettingsForm() {
  const [settings, setSettings] = useState<BackupSettings | null>(null)
  const [enabled, setEnabled] = useState(false)
  const [days, setDays] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .backupSettings()
      .then((data) => {
        if (cancelled) return
        setSettings(data)
        setEnabled(data.enabled)
        setDays(minutesToDays(data.interval_minutes))
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "خطایی رخ داد.")
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function save() {
    const interval = Number(days)
    if (
      days.trim() === "" ||
      !Number.isInteger(interval) ||
      interval < MIN_DAYS ||
      interval > MAX_DAYS
    ) {
      setError(
        `فاصله باید ${formatPersianNumber(MIN_DAYS)} تا ${formatPersianNumber(MAX_DAYS)} روز باشد.`
      )
      setSaved(false)
      return
    }
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateBackupSettings({
        enabled,
        interval_minutes: interval * MINUTES_PER_DAY,
      })
      setSettings(data)
      setEnabled(data.enabled)
      setDays(minutesToDays(data.interval_minutes))
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (settings === null && error === null) {
    return (
      <div
        className="h-20 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium">پشتیبان خودکار</span>
        <Button
          type="button"
          variant={enabled ? "default" : "outline"}
          aria-pressed={enabled}
          onClick={() => {
            setEnabled((current) => !current)
            setSaved(false)
          }}
          className="h-9"
        >
          {enabled ? "فعال" : "غیرفعال"}
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <Input
          value={days === "" ? "" : formatPersianNumber(days)}
          onChange={(event) => {
            setDays(parseDaysInput(event.target.value))
            setSaved(false)
          }}
          placeholder="مثلاً ۷"
          aria-label="فاصله پشتیبان گیری خودکار (روز)"
          inputMode="numeric"
          maxLength={2}
          className="h-11 w-20 shrink-0 text-center md:h-9 md:w-24"
        />
        <span className="shrink-0 text-sm text-muted-foreground">روز</span>
        <Button
          onClick={() => void save()}
          disabled={busy}
          aria-busy={busy}
          className="h-11 gap-2 md:h-9"
        >
          <BusyLabel
            busy={busy}
            idle="ذخیره"
            busyLabel={<span className="sr-only">در حال ذخیره…</span>}
            spinner
          />
        </Button>
      </div>
      {settings && (!settings.tools_available || !settings.storage_ready) ? (
        <div
          role="alert"
          className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm leading-6 text-destructive ring-1 ring-destructive/20"
        >
          {!settings.tools_available
            ? "ابزارهای PostgreSQL نصب نیستند؛ ساخت و بازیابی نسخه ممکن نیست."
            : null}
          {!settings.storage_ready
            ? "پوشه ذخیره پشتیبان قابل نوشتن نیست."
            : null}
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {toPersianDigits(error)}
        </p>
      ) : null}
      {saved ? (
        <p role="status" className="text-sm text-success">
          ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
