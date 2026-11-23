"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { toast } from "@workspace/ui/primitives/sonner"
import {
  formatPersianNumber,
  parsePriceFilterInput,
} from "@workspace/ui/lib/number"

import { api } from "@/lib/api"

export function InventoryThresholdSettings() {
  const [value, setValue] = useState("")
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (!cancelled) {
          setValue(String(data.low_stock_threshold))
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
    const raw = value.trim()
    if (raw === "") {
      toast.error("آستانه را وارد کنید.")
      return
    }
    const threshold = Number(raw)
    if (!Number.isInteger(threshold) || threshold < 0) {
      toast.error("آستانه باید عدد صحیح نامنفی باشد.")
      return
    }
    setBusy(true)
    try {
      const data = await api.updateSettings({ low_stock_threshold: threshold })
      setValue(String(data.low_stock_threshold))
      toast.success("آستانه موجودی کم ذخیره شد.")
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
          onChange={(e) => setValue(parsePriceFilterInput(e.target.value))}
          placeholder="مثلاً ۱۰"
          aria-label="آستانه موجودی کم (عدد)"
          inputMode="numeric"
          maxLength={7}
          className="h-11 sm:h-8"
        />
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
