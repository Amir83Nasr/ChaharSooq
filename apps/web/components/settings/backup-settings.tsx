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

const MIN_HOURS = 1
const MAX_HOURS = 168

const VERIFICATION_LABELS: Record<string, string> = {
  pg_restore_list: "بررسی ساختار آرشیو",
  decrypt_list: "بررسی فهرست فایل",
  drill_restore: "آزمون بازیابی",
}

function verificationLabel(method: string): string {
  return VERIFICATION_LABELS[method] ?? toPersianDigits(method)
}

function minutesToHours(minutes: number): string {
  return String(Number((minutes / 60).toFixed(2)))
}

function parseHoursInput(value: string): string {
  const digits = toLatinDigits(value).replace(/٫/g, ".").replace(/٬/g, "")
  const cleaned = digits.replace(/[^0-9.]/g, "")
  const dot = cleaned.indexOf(".")
  if (dot === -1) return cleaned.slice(0, 3)
  const integer = cleaned.slice(0, dot).slice(0, 3)
  const fraction = cleaned
    .slice(dot + 1)
    .replace(/\./g, "")
    .slice(0, 2)
  return fraction.length > 0 ? `${integer || "0"}.${fraction}` : `${integer}.`
}

/** Owner-only automatic backup toggle and interval editor. */
export function BackupSettingsForm() {
  const [settings, setSettings] = useState<BackupSettings | null>(null)
  const [enabled, setEnabled] = useState(false)
  const [hours, setHours] = useState("")
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
        setHours(minutesToHours(data.interval_minutes))
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
    const value = toLatinDigits(hours).replace(/٫/g, ".")
    const interval = Number(value)
    if (
      value.trim() === "" ||
      !Number.isFinite(interval) ||
      interval < MIN_HOURS ||
      interval > MAX_HOURS
    ) {
      setError(
        `فاصله باید ${formatPersianNumber(MIN_HOURS)} تا ${formatPersianNumber(MAX_HOURS)} ساعت باشد.`
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
        interval_minutes: Math.round(interval * 60),
      })
      setSettings(data)
      setEnabled(data.enabled)
      setHours(minutesToHours(data.interval_minutes))
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
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={hours === "" ? "" : formatPersianNumber(hours)}
          onChange={(event) => {
            setHours(parseHoursInput(event.target.value))
            setSaved(false)
          }}
          placeholder="مثلاً ۱۲"
          aria-label="فاصلهٔ پشتیبان‌گیری خودکار (ساعت)"
          inputMode="decimal"
          maxLength={6}
          className="h-11 sm:h-8 sm:max-w-36"
        />
        <span className="text-sm text-muted-foreground">ساعت</span>
        <Button
          onClick={() => void save()}
          disabled={busy}
          aria-busy={busy}
          className="h-11 sm:h-8"
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
            ? "پوشهٔ ذخیرهٔ پشتیبان قابل نوشتن نیست."
            : null}
        </div>
      ) : null}
      {settings ? (
        <p className="text-sm leading-6 text-muted-foreground">
          نگهداری {formatPersianNumber(settings.retention_days)} روز · تأیید{" "}
          {verificationLabel(settings.verification_method)} · ذخیره روی همین
          سرور.
        </p>
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
