"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import {
  formatPersianNumber,
  toLatinDigits,
  toPersianDigits,
} from "@workspace/ui/lib/number"

import { api } from "@/lib/api"

function minutesToHoursInput(minutes: number): string {
  if (Number.isFinite(minutes) && minutes % 60 === 0) {
    return String(minutes / 60)
  }
  const hours = minutes / 60
  return String(Number(hours.toFixed(2)))
}

function parseHoursInput(value: string): string {
  const withDot = toLatinDigits(value).replace(/٫/g, ".").replace(/٬/g, "")
  const cleaned = withDot.replace(/[^0-9.]/g, "")
  const dot = cleaned.indexOf(".")
  if (dot === -1) return cleaned.slice(0, 3)
  const intPart = cleaned.slice(0, dot).slice(0, 3)
  const fracPart = cleaned
    .slice(dot + 1)
    .replace(/\./g, "")
    .slice(0, 2)
  return fracPart.length > 0 ? `${intPart || "0"}.${fracPart}` : `${intPart}.`
}

export function CompetitorSyncIntervalSettings() {
  const [value, setValue] = useState("")
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (!cancelled) {
          setValue(minutesToHoursInput(data.competitor_sync_interval_minutes))
          setLoaded(true)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "خطایی رخ داد.")
          setLoaded(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function save() {
    const raw = value.trim().replace(/٫/g, ".")
    if (raw === "" || raw === ".") {
      setError("فاصله را وارد کنید.")
      setSaved(false)
      return
    }
    const hours = Number(raw)
    if (!Number.isFinite(hours) || hours < 1 || hours > 168) {
      setError("فاصله باید عددی بین ۱ تا ۱۶۸ ساعت باشد.")
      setSaved(false)
      return
    }
    const minutes = Math.round(hours * 60)
    if (minutes < 15 || minutes > 10080) {
      setError("فاصله باید عددی بین ۱ تا ۱۶۸ ساعت باشد.")
      setSaved(false)
      return
    }
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings({
        competitor_sync_interval_minutes: minutes,
      })
      setValue(minutesToHoursInput(data.competitor_sync_interval_minutes))
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-10 animate-pulse rounded-md bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Input
          value={value === "" ? "" : formatPersianNumber(value)}
          onChange={(e) => {
            setValue(parseHoursInput(e.target.value))
            setSaved(false)
          }}
          placeholder="مثلاً ۲۴"
          aria-label="فاصله به‌روزرسانی خودکار قیمت رقبا (ساعت)"
          inputMode="decimal"
          maxLength={6}
        />
        <span className="text-sm text-muted-foreground">ساعت</span>
        <Button onClick={save} disabled={busy || value.trim() === ""}>
          ذخیره
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {toPersianDigits(error)}
        </p>
      ) : null}
      {saved ? (
        <p
          role="status"
          className="text-sm text-emerald-600 dark:text-emerald-400"
        >
          فاصله به‌روزرسانی ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
