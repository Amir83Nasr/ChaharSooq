"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { Price } from "@workspace/ui/persian/price"

import { ApiRequestError, api, type ProductOut } from "@/lib/api"

function parsePercent(raw: string): {
  value: number | null
  error: string | null
} {
  const trimmed = raw.trim()
  if (trimmed === "") return { value: null, error: null }
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    return { value: null, error: "عددی بین ۰ تا ۱۰۰ وارد کنید." }
  }
  return { value, error: null }
}

function toInput(value: number | null): string {
  return value === null ? "" : String(Math.round(value * 100) / 100)
}

function toPersianError(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "ذخیرهٔ محدوده انجام نشد. دوباره تلاش کنید."
}

export function ProductPriceBounds({
  product,
  canEdit = true,
  onChanged,
  onSaved,
}: {
  product: ProductOut
  canEdit?: boolean
  onChanged?: () => void
  onSaved?: (product: ProductOut) => void
}) {
  const [decrease, setDecrease] = useState(() =>
    toInput(product.allowed_decrease_percent)
  )
  const [increase, setIncrease] = useState(() =>
    toInput(product.allowed_increase_percent)
  )
  const [savedDecrease, setSavedDecrease] = useState(() =>
    toInput(product.allowed_decrease_percent)
  )
  const [savedIncrease, setSavedIncrease] = useState(() =>
    toInput(product.allowed_increase_percent)
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const nextDecrease = toInput(product.allowed_decrease_percent)
    const nextIncrease = toInput(product.allowed_increase_percent)
    setDecrease(nextDecrease)
    setIncrease(nextIncrease)
    setSavedDecrease(nextDecrease)
    setSavedIncrease(nextIncrease)
    setError(null)
  }, [
    product.id,
    product.allowed_decrease_percent,
    product.allowed_increase_percent,
  ])

  const decreaseParsed = parsePercent(decrease)
  const increaseParsed = parsePercent(increase)
  const fieldError = decreaseParsed.error ?? increaseParsed.error
  const isDirty =
    decrease.trim() !== savedDecrease.trim() ||
    increase.trim() !== savedIncrease.trim()

  const floor =
    decreaseParsed.value === null
      ? null
      : Math.round(product.price * (1 - decreaseParsed.value / 100))
  const ceiling =
    increaseParsed.value === null
      ? null
      : Math.round(product.price * (1 + increaseParsed.value / 100))

  async function save() {
    if (fieldError || busy || !isDirty) return
    const decreaseValue = decreaseParsed.value
    const increaseValue = increaseParsed.value
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await api.updateProductPriceBounds(product.id, {
        allowed_decrease_percent: decreaseValue,
        allowed_increase_percent: increaseValue,
      })
      setSavedDecrease(toInput(decreaseValue))
      setSavedIncrease(toInput(increaseValue))
      setSaved(true)
      onSaved?.(updated)
      onChanged?.()
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setBusy(false)
    }
  }

  if (!canEdit) {
    return (
      <section className="space-y-2 rounded-2xl border border-border bg-muted/30 p-4">
        <h3 className="font-semibold">حدود قیمت پیشنهادی</h3>
        <p className="text-xs leading-5 text-muted-foreground">
          کف مجاز: {floor === null ? "بدون محدودیت" : <Price value={floor} />} ·
          سقف مجاز:{" "}
          {ceiling === null ? "بدون محدودیت" : <Price value={ceiling} />}
        </p>
      </section>
    )
  }

  return (
    <section className="space-y-4 rounded-2xl border border-border bg-muted/30 p-4 text-start">
      <div className="space-y-1">
        <h3 className="font-semibold">حدود قیمت پیشنهادی</h3>
        <p className="text-xs leading-5 text-muted-foreground">
          قیمت پیشنهادی هرگز از کف و سقف زیر خارج نمی‌شود. خالی گذاشتن هر فیلد
          یعنی آن سمت محدودیتی ندارد.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            حداکثر کاهش زیر قیمت پایه (m)
          </span>
          <span className="relative block">
            <Input
              type="number"
              inputMode="decimal"
              min={0}
              max={100}
              step={0.5}
              dir="ltr"
              value={decrease}
              onChange={(event) => {
                setDecrease(event.target.value)
                setSaved(false)
                setError(null)
              }}
              placeholder="مثلاً 5"
              aria-label="حداکثر کاهش مجاز درصدی"
              aria-invalid={decreaseParsed.error ? true : undefined}
              className="[appearance:textfield] ps-9 text-left tabular-nums [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="pointer-events-none absolute inset-y-0 start-3 flex items-center text-xs text-muted-foreground">
              ٪
            </span>
          </span>
        </label>
        <label className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            حداکثر افزایش بالای قیمت پایه (n)
          </span>
          <span className="relative block">
            <Input
              type="number"
              inputMode="decimal"
              min={0}
              max={100}
              step={0.5}
              dir="ltr"
              value={increase}
              onChange={(event) => {
                setIncrease(event.target.value)
                setSaved(false)
                setError(null)
              }}
              placeholder="مثلاً 10"
              aria-label="حداکثر افزایش مجاز درصدی"
              aria-invalid={increaseParsed.error ? true : undefined}
              className="[appearance:textfield] ps-9 text-left tabular-nums [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="pointer-events-none absolute inset-y-0 start-3 flex items-center text-xs text-muted-foreground">
              ٪
            </span>
          </span>
        </label>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-background px-3 py-2">
          <p className="text-[11px] text-muted-foreground">
            کف = Pb × (1 − m/100)
          </p>
          <p className="mt-0.5 text-sm font-semibold">
            {floor === null ? "بدون محدودیت" : <Price value={floor} />}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-background px-3 py-2">
          <p className="text-[11px] text-muted-foreground">
            سقف = Pb × (1 + n/100)
          </p>
          <p className="mt-0.5 text-sm font-semibold">
            {ceiling === null ? "بدون محدودیت" : <Price value={ceiling} />}
          </p>
        </div>
      </div>

      {fieldError ? (
        <p role="alert" className="text-xs text-destructive">
          {fieldError}
        </p>
      ) : error ? (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          disabled={busy || !isDirty || fieldError !== null}
          onClick={() => void save()}
          aria-busy={busy}
          className="h-11 rounded-2xl sm:h-9"
        >
          <BusyLabel
            busy={busy}
            idle="ذخیرهٔ محدوده"
            busyLabel="در حال ذخیره…"
            spinner
          />
        </Button>
        {saved ? (
          <span role="status" className="text-xs text-success">
            محدوده ذخیره شد.
          </span>
        ) : isDirty ? (
          <span className="text-xs text-amber-700 dark:text-amber-300">
            تغییرات ذخیره نشده است.
          </span>
        ) : null}
      </div>

      {product.price > 0 ? (
        <p className="text-[11px] text-muted-foreground">
          قیمت پایه: <Price value={product.price} /> — بازه مجاز از{" "}
          {floor === null ? "بدون کف" : <Price value={floor} />} تا{" "}
          {ceiling === null ? "بدون سقف" : <Price value={ceiling} />}
        </p>
      ) : null}
    </section>
  )
}
