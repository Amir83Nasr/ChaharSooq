"use client"

import { useEffect, useState } from "react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"

import { api, type CategoryOut, type SuggestedPriceFormula } from "@/lib/api"

export function SuggestedPriceSettings() {
  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [formulas, setFormulas] = useState<SuggestedPriceFormula[]>([])
  const [categoryToAdd, setCategoryToAdd] = useState("")
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.categories(), api.settings()])
      .then(([categoryRows, settings]) => {
        if (cancelled) return
        setCategories(categoryRows)
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

  const configured = new Set(formulas.map((formula) => formula.category_id))
  const available = categories.filter(
    (category) => !configured.has(category.id)
  )

  function updateFormula(categoryId: number, expression: string) {
    setFormulas((current) =>
      current.map((formula) =>
        formula.category_id === categoryId
          ? { ...formula, expression }
          : formula
      )
    )
    setSaved(false)
  }

  function addFormula() {
    const categoryId = Number(categoryToAdd)
    if (!categoryId) return
    setFormulas((current) => [
      ...current,
      { category_id: categoryId, expression: "x" },
    ])
    setCategoryToAdd("")
    setSaved(false)
  }

  async function save() {
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings({
        suggested_price_formulas: formulas,
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
      {formulas.map((formula) => {
        const category = categories.find(
          (item) => item.id === formula.category_id
        )
        return (
          <div
            key={formula.category_id}
            className="flex flex-col gap-2 sm:flex-row sm:items-center"
          >
            <label
              className="min-w-36 text-sm"
              htmlFor={`formula-${formula.category_id}`}
            >
              {category?.name ?? `دسته ${formula.category_id}`}
            </label>
            <Input
              id={`formula-${formula.category_id}`}
              dir="ltr"
              className="text-left"
              value={formula.expression}
              onChange={(event) =>
                updateFormula(formula.category_id, event.target.value)
              }
              placeholder="مثلاً x * 1.05"
              aria-label={`فرمول قیمت پیشنهادی ${category?.name ?? "دسته‌بندی"}`}
              maxLength={256}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setFormulas((current) =>
                  current.filter(
                    (item) => item.category_id !== formula.category_id
                  )
                )
                setSaved(false)
              }}
              disabled={busy}
            >
              حذف
            </Button>
          </div>
        )
      })}
      {available.length > 0 ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={categoryToAdd}
            onChange={(event) => setCategoryToAdd(event.target.value)}
            aria-label="انتخاب دسته‌بندی برای افزودن فرمول"
          >
            <option value="">انتخاب دسته‌بندی</option>
            {available.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            onClick={addFormula}
            disabled={!categoryToAdd || busy}
          >
            افزودن فرمول
          </Button>
        </div>
      ) : categories.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          برای تعریف فرمول ابتدا دسته‌بندی ایجاد کنید.
        </p>
      ) : null}
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
