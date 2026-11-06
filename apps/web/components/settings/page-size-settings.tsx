"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { PersianNumber } from "@workspace/ui/persian/persian-number"

import { api } from "@/lib/api"

export const PAGE_SIZE_OPTIONS = [0, 10, 100, 500] as const

export function PageSizeSettings() {
  const [value, setValue] = useState<number | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [savingValue, setSavingValue] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (!cancelled) {
          setValue(data.default_page_size)
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

  async function save(next: number) {
    if (busy || next === value) return
    setBusy(true)
    setSavingValue(next)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings({ default_page_size: next })
      setValue(data.default_page_size)
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
      setSavingValue(null)
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
      <div
        className="grid grid-cols-2 gap-2 sm:grid-cols-4"
        role="radiogroup"
        aria-label="تعداد ردیف پیش‌فرض"
      >
        {PAGE_SIZE_OPTIONS.map((n) => {
          const active = value === n
          return (
            <Button
              key={n}
              variant={active ? "default" : "outline"}
              role="radio"
              aria-checked={active}
              disabled={busy}
              aria-busy={savingValue === n}
              onClick={() => save(n)}
              className="h-11 md:h-9"
            >
              <BusyLabel
                busy={savingValue === n}
                idle={
                  n === 0 ? (
                    "همه"
                  ) : (
                    <span className="inline-flex items-center gap-1">
                      <PersianNumber value={n} />
                      <span>ردیف</span>
                    </span>
                  )
                }
                busyLabel={<span className="sr-only">در حال ذخیره…</span>}
                spinner
              />
            </Button>
          )
        })}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p role="status" className="text-sm text-success">
          تعداد پیش‌فرض ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
