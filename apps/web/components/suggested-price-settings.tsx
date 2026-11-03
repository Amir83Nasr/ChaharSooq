"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"

import { api, type SuggestedPriceFormula, type TopGroup } from "@/lib/api"

const TOP_GROUPS: TopGroup[] = ["فرش", "مبلمان", "لوازم خانگی"]

export function SuggestedPriceSettings() {
  const [formulas, setFormulas] = useState<SuggestedPriceFormula[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((settings) => {
        if (cancelled) return
        setFormulas(settings.suggested_price_formulas)
        setLoaded(true)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "خطایی رخ داد.")
        setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function expressionFor(topGroup: TopGroup): string {
    return (
      formulas.find((formula) => formula.top_group === topGroup)?.expression ??
      ""
    )
  }

  function updateFormula(topGroup: TopGroup, expression: string) {
    setFormulas((current) => {
      if (current.some((formula) => formula.top_group === topGroup)) {
        return current.map((formula) =>
          formula.top_group === topGroup ? { ...formula, expression } : formula
        )
      }
      return [...current, { top_group: topGroup, expression }]
    })
    setSaved(false)
  }

  async function save() {
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const payload = formulas.filter(
        (formula) => formula.expression.trim() !== ""
      )
      const data = await api.updateSettings({
        suggested_price_formulas: payload,
      })
      setFormulas(data.suggested_price_formulas)
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
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        برای هر دسته‌بندی می‌توانید عبارت ریاضی قیمت پیشنهادی را با متغیر x
        تعریف کنید. منبع و مقدار روزانه x پس از مشخص‌شدن اتصال داده، به این
        فرمول وصل می‌شود.
      </p>
      {TOP_GROUPS.map((topGroup) => (
        <div
          key={topGroup}
          className="flex flex-col gap-2 sm:flex-row sm:items-center"
        >
          <label className="min-w-36 text-sm" htmlFor={`formula-${topGroup}`}>
            {topGroup}
          </label>
          <Input
            id={`formula-${topGroup}`}
            dir="ltr"
            className="text-left"
            value={expressionFor(topGroup)}
            onChange={(event) => updateFormula(topGroup, event.target.value)}
            placeholder="مثلاً x * 1.05"
            aria-label={`فرمول قیمت پیشنهادی ${topGroup}`}
            maxLength={256}
          />
        </div>
      ))}
      <div>
        <Button onClick={save} disabled={busy}>
          {busy ? "در حال ذخیره…" : "ذخیره فرمول‌ها"}
        </Button>
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
          فرمول‌ها ذخیره شدند.
        </p>
      ) : null}
    </div>
  )
}
