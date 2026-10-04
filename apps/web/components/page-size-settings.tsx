"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { cn } from "@workspace/ui/lib/utils"

import { api } from "@/lib/api"

export const PAGE_SIZE_OPTIONS = [10, 20, 50] as const

export function PageSizeSettings() {
  const [value, setValue] = useState<number | null>(null)
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
    }
  }

  if (!loaded) {
    return <div className="h-10 animate-pulse rounded-md bg-muted" aria-label="در حال بارگذاری" />
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        جدول محصولات در بارگذاری اول با این تعداد ردیف نمایش داده می‌شود.
      </p>
      <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="تعداد ردیف پیش‌فرض">
        {PAGE_SIZE_OPTIONS.map((n) => {
          const active = value === n
          return (
            <Button
              key={n}
              variant={active ? "default" : "outline"}
              role="radio"
              aria-checked={active}
              disabled={busy}
              onClick={() => save(n)}
              className={cn("h-10")}
            >
              <PersianNumber value={n} />
              <span>ردیف</span>
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
        <p role="status" className="text-sm text-emerald-600 dark:text-emerald-400">
          تعداد پیش‌فرض ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
