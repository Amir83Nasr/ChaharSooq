"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import {
  formatPersianNumber,
  parsePriceFilterInput,
  toPersianDigits,
} from "@workspace/ui/lib/number"

import { api } from "@/lib/api"

export function SyncIntervalSettings() {
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
          setValue(String(data.sync_interval_minutes))
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
      setError("فاصله را وارد کنید.")
      setSaved(false)
      return
    }
    const minutes = Number(raw)
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 10080) {
      setError("فاصله باید عدد صحیح بین ۱ تا ۱۰۰۸۰ دقیقه باشد.")
      setSaved(false)
      return
    }
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings({ sync_interval_minutes: minutes })
      setValue(String(data.sync_interval_minutes))
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
      <p className="text-sm text-muted-foreground">
        هر چند دقیقه یکبار کاتالوگ محصولات به‌طور خودکار از حسابداری به‌روز شود.
        مثلاً ۱۲۰ برای هر ۲ ساعت.
      </p>
      <div className="flex items-center gap-2">
        <Input
          value={value === "" ? "" : formatPersianNumber(value)}
          onChange={(e) => {
            setValue(parsePriceFilterInput(e.target.value))
            setSaved(false)
          }}
          placeholder="مثلاً ۱۲۰"
          aria-label="فاصله به‌روزرسانی خودکار (دقیقه)"
          inputMode="numeric"
          maxLength={5}
        />
        <span className="text-sm text-muted-foreground">دقیقه</span>
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
