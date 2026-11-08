"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { Price } from "@workspace/ui/persian/price"
import { DECIMAL_SEP } from "@workspace/ui/lib/locale"
import { formatPersianNumber, toLatinDigits } from "@workspace/ui/lib/number"
import { cn } from "@workspace/ui/lib/utils"

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

/** Keeps the field numeric while the user types; the value stays machine-readable. */
function normalizePercentInput(raw: string): string {
  const latin = toLatinDigits(raw)
    .replace(DECIMAL_SEP, ".")
    .replace(/[^\d.]/g, "")
  if (!/\d/.test(latin)) return ""
  const [whole = "", ...fractionParts] = latin.split(".")
  const fraction = fractionParts.join("").slice(0, 2)
  const integer = whole.slice(0, 3) || "0"
  return latin.includes(".") ? `${integer}.${fraction}` : integer
}

function toInput(value: number | null): string {
  return value === null ? "" : String(Math.round(value * 100) / 100)
}

function toPersianError(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "ذخیرهٔ محدوده انجام نشد. دوباره تلاش کنید."
}

function PercentField({
  id,
  label,
  hint,
  value,
  placeholder,
  invalid,
  error,
  onChange,
}: {
  id: string
  label: string
  hint: string
  value: string
  placeholder: string
  invalid: boolean
  error: string | null
  onChange: (value: string) => void
}) {
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={id}
        className="flex items-baseline justify-between gap-1.5"
      >
        <span className="text-xs font-medium text-foreground">{label}</span>
        <span className="text-[10px] text-muted-foreground">{hint}</span>
      </label>
      <div
        className={cn(
          "flex h-10 items-stretch overflow-hidden rounded-2xl border border-input bg-background transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50",
          invalid && "border-destructive ring-3 ring-destructive/20"
        )}
      >
        <span
          aria-hidden="true"
          className="flex w-9 shrink-0 items-center justify-center border-e border-input bg-muted/40 text-sm font-medium text-muted-foreground"
        >
          ٪
        </span>
        <Input
          id={id}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={value === "" ? "" : formatPersianNumber(value)}
          onChange={(event) =>
            onChange(normalizePercentInput(event.target.value))
          }
          placeholder={placeholder}
          aria-invalid={invalid || undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          className="h-full flex-1 rounded-none border-0 bg-transparent px-3 text-start text-sm tabular-nums shadow-none focus-visible:ring-0"
        />
      </div>
      {error ? (
        <p
          id={`${id}-error`}
          role="alert"
          className="text-[11px] leading-4 text-destructive"
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}

function BoundsResult({
  floor,
  ceiling,
}: {
  floor: number | null
  ceiling: number | null
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border bg-background px-3 py-2 text-[11px] text-muted-foreground">
      <span className="inline-flex items-baseline gap-1">
        کف مجاز:
        {floor === null ? (
          <span>بدون محدودیت</span>
        ) : (
          <Price
            value={floor}
            className="text-xs font-semibold text-foreground"
          />
        )}
      </span>
      <span aria-hidden="true" className="text-border">
        |
      </span>
      <span className="inline-flex items-baseline gap-1">
        سقف مجاز:
        {ceiling === null ? (
          <span>بدون محدودیت</span>
        ) : (
          <Price
            value={ceiling}
            className="text-xs font-semibold text-foreground"
          />
        )}
      </span>
    </div>
  )
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
      <section className="space-y-2 rounded-2xl border border-border bg-muted/30 px-3 py-2.5 text-start">
        <h3 className="text-sm font-semibold">حدود قیمت پیشنهادی</h3>
        <BoundsResult floor={floor} ceiling={ceiling} />
      </section>
    )
  }

  return (
    <section className="space-y-3 rounded-2xl border border-border bg-muted/30 p-3 text-start">
      <div className="space-y-0.5">
        <h3 className="text-sm font-semibold">حدود قیمت پیشنهادی</h3>
        <p className="text-[11px] leading-4 text-muted-foreground">
          قیمت پیشنهادی از این کف و سقف خارج نمی‌شود؛ خالی گذاشتن هر فیلد یعنی
          بدون محدودیت.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <PercentField
          id="allowed-decrease-percent"
          label="حداکثر کاهش"
          hint="زیر قیمت پایه"
          value={decrease}
          placeholder="مثلاً ۵"
          invalid={decreaseParsed.error !== null}
          error={decreaseParsed.error}
          onChange={(value) => {
            setDecrease(value)
            setSaved(false)
            setError(null)
          }}
        />
        <PercentField
          id="allowed-increase-percent"
          label="حداکثر افزایش"
          hint="بالای قیمت پایه"
          value={increase}
          placeholder="مثلاً ۱۰"
          invalid={increaseParsed.error !== null}
          error={increaseParsed.error}
          onChange={(value) => {
            setIncrease(value)
            setSaved(false)
            setError(null)
          }}
        />
      </div>

      <BoundsResult floor={floor} ceiling={ceiling} />

      {error ? (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={busy || !isDirty || fieldError !== null}
          onClick={() => void save()}
          aria-busy={busy}
          className="h-9 rounded-2xl px-4"
        >
          <BusyLabel
            busy={busy}
            idle="ذخیره محدوده"
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
    </section>
  )
}
