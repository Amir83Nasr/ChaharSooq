"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { formatPersianNumber, parsePriceFilterInput, toPersianDigits } from "@workspace/ui/lib/number"

import { api } from "@/lib/api"

export function InventoryThresholdSettings() {
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
          setValue(String(data.low_stock_threshold))
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
    const raw = value.trim()
    if (raw === "") {
      setError("آستانه را وارد کنید.")
      setSaved(false)
      return
    }
    const threshold = Number(raw)
    if (!Number.isInteger(threshold) || threshold < 0) {
      setError("آستانه باید عدد صحیح نامنفی باشد.")
      setSaved(false)
      return
    }
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings(threshold)
      setValue(String(data.low_stock_threshold))
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return <div className="h-10 animate-pulse rounded-md bg-muted" aria-label="در حال بارگذاری" />
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        کالایی که موجودی آن از این عدد کمتر یا مساوی باشد، «کم» محسوب می‌شود.
      </p>
      <div className="flex items-center gap-2">
        <Input
          value={value === "" ? "" : formatPersianNumber(value)}
          onChange={(e) => {
            setValue(parsePriceFilterInput(e.target.value))
            setSaved(false)
          }}
          placeholder="مثلاً ۱۰"
          aria-label="آستانه موجودی کم (عدد)"
          inputMode="numeric"
          maxLength={7}
        />
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
        <p role="status" className="text-sm text-emerald-600 dark:text-emerald-400">
          آستانه ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
