"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/primitives/button"

import { api, type DefaultCompetitorStore } from "@/lib/api"

const OPTIONS: { value: DefaultCompetitorStore; label: string }[] = [
  { value: "digikala", label: "دیجی‌کالا" },
  { value: "technolife", label: "تکنولایف" },
]

export function CompetitorStoreSettings() {
  const [value, setValue] = useState<DefaultCompetitorStore | null>(null)
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
          setValue(data.default_competitor_store)
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

  async function save(next: DefaultCompetitorStore) {
    if (busy || next === value) return
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings({ default_competitor_store: next })
      setValue(data.default_competitor_store)
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
      <div
        className="grid grid-cols-2 gap-2"
        role="radiogroup"
        aria-label="بازار پیش‌فرض قیمت رقبا"
      >
        {OPTIONS.map((option) => {
          const active = value === option.value
          return (
            <Button
              key={option.value}
              variant={active ? "default" : "outline"}
              role="radio"
              aria-checked={active}
              disabled={busy}
              onClick={() => save(option.value)}
            >
              {option.label}
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
        <p
          role="status"
          className="text-sm text-emerald-600 dark:text-emerald-400"
        >
          بازار پیش‌فرض ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
