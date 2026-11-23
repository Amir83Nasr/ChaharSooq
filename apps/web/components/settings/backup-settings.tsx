"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { toast } from "@workspace/ui/primitives/sonner"
import { formatPersianNumber, toLatinDigits } from "@workspace/ui/lib/number"

import { api, type BackupSettings } from "@/lib/api"
import { BackupUnavailableNotice } from "./backup-unavailable-notice"

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
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .backupSettings()
      .then((data) => {
        if (cancelled) return
        setSettings(data)
        setEnabled(data.enabled)
        setDays(minutesToDays(data.interval_minutes))
        setLoaded(true)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
          setLoaded(true)
        }
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
      toast.error(
        `فاصله باید ${formatPersianNumber(MIN_DAYS)} تا ${formatPersianNumber(MAX_DAYS)} روز باشد.`
      )
      return
    }
    setBusy(true)
    try {
      const data = await api.updateBackupSettings({
        enabled,
        interval_minutes: interval * MINUTES_PER_DAY,
      })
      setSettings(data)
      setEnabled(data.enabled)
      setDays(minutesToDays(data.interval_minutes))
      toast.success("تنظیمات پشتیبان خودکار ذخیره شد.")
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-20 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  const unavailable = settings
    ? !settings.tools_available || !settings.storage_ready
    : false

  return (
    <div className="flex flex-col gap-4">
      {settings ? (
        <BackupUnavailableNotice
          toolsAvailable={settings.tools_available}
          storageReady={settings.storage_ready}
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium">پشتیبان خودکار</span>
        <Button
          type="button"
          variant={enabled ? "default" : "outline"}
          aria-pressed={enabled}
          disabled={unavailable}
          onClick={() => {
            setEnabled((current) => !current)
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
          disabled={busy || unavailable}
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
    </div>
  )
}
