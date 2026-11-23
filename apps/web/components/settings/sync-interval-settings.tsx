"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { toast } from "@workspace/ui/primitives/sonner"
import { formatPersianNumber, toLatinDigits } from "@workspace/ui/lib/number"

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

export function SyncIntervalSettings() {
  const [value, setValue] = useState("")
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (!cancelled) {
          setValue(minutesToHoursInput(data.sync_interval_minutes))
          setLoaded(true)
        }
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
    const raw = value.trim().replace(/٫/g, ".")
    if (raw === "" || raw === ".") {
      toast.error("فاصله را وارد کنید.")
      return
    }
    const hours = Number(raw)
    if (!Number.isFinite(hours) || hours < 1 || hours > 168) {
      toast.error("فاصله باید عددی بین ۱ تا ۱۶۸ ساعت باشد.")
      return
    }
    const minutes = Math.round(hours * 60)
    if (minutes < 1 || minutes > 10080) {
      toast.error("فاصله باید عددی بین ۱ تا ۱۶۸ ساعت باشد.")
      return
    }
    setBusy(true)
    try {
      const data = await api.updateSettings({ sync_interval_minutes: minutes })
      setValue(minutesToHoursInput(data.sync_interval_minutes))
      toast.success("فاصله به‌روزرسانی ذخیره شد.")
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-10 animate-pulse rounded-2xl bg-muted"
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
          }}
          placeholder="مثلاً ۲۴"
          aria-label="فاصله به‌روزرسانی خودکار (ساعت)"
          inputMode="decimal"
          maxLength={6}
          className="h-11 sm:h-8"
        />
        <span className="text-sm text-muted-foreground">ساعت</span>
        <Button
          onClick={save}
          disabled={busy || value.trim() === ""}
          aria-busy={busy}
          className="h-11 shrink-0 sm:h-8"
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
