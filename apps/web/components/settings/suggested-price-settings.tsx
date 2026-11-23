"use client"

import { useEffect, useState } from "react"
import { Info, Minus, Plus, RefreshCw, X } from "lucide-react"

import { formatPersianNumber } from "@workspace/ui/lib/number"
import { Badge } from "@workspace/ui/primitives/badge"
import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { toast } from "@workspace/ui/primitives/sonner"

import { api, type PricingMode, type SuggestedPriceFormula } from "@/lib/api"

type WeightInputs = Partial<Record<PricingMode, string>>
type FieldErrors = Partial<Record<PricingMode, string>>

const WEIGHT_STEP = 0.05

interface ModeConfig {
  mode: PricingMode
  id: string
  label: string
  range: string
  hint: string
}

const MODES: ModeConfig[] = [
  {
    mode: "exact_competitor",
    id: "exact_competitor",
    label: "قیمت رقیب",
    range: "۰٫۴ تا ۰٫۶",
    hint: "وزن سهم قیمت رقیب دقیق در فرمول پیشنهادی.",
  },
  {
    mode: "similar_product",
    id: "similar_product",
    label: "محصول مشابه",
    range: "۰٫۱ تا ۰٫۳",
    hint: "وزن سهم تغییر روزانه قیمت محصول مشابه در فرمول پیشنهادی.",
  },
]

function isTrackingMode(mode: PricingMode): boolean {
  return mode === "similar_product"
}

interface ParsedWeight {
  value: number | null
  error: string | null
}

function parseWeight(raw: string): ParsedWeight {
  const trimmed = raw.trim()
  if (trimmed === "") return { value: null, error: null }
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    return { value: null, error: "عددی بین ۰ و ۱ وارد کنید." }
  }
  return { value, error: null }
}

function formatWeight(value: number): string {
  return formatPersianNumber(Math.round(value * 1000) / 1000)
}

function formatPercent(value: number): string {
  return `${formatPersianNumber(Math.round(value * 100))}٪`
}

function clampWeight(value: number): number {
  return Math.min(1, Math.max(0, Math.round(value * 10000) / 10000))
}

function stepWeight(current: string, delta: number): string {
  const { value } = parseWeight(current)
  return String(clampWeight((value ?? 0) + delta))
}

function inputsFromFormulas(formulas: SuggestedPriceFormula[]): WeightInputs {
  const inputs: WeightInputs = {}
  for (const formula of formulas) {
    inputs[formula.mode] = String(formula.weight)
  }
  return inputs
}

export function SuggestedPriceSettings() {
  const [weights, setWeights] = useState<WeightInputs>({})
  const [savedWeights, setSavedWeights] = useState<WeightInputs>({})
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoaded(false)
    setLoadError(null)
    api
      .settings()
      .then((settings) => {
        if (cancelled) return
        const next = inputsFromFormulas(settings.suggested_price_formulas)
        setWeights(next)
        setSavedWeights(next)
        setFieldErrors({})
        setLoaded(true)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : "خطایی رخ داد."
        setLoadError(message)
        toast.error(message)
        setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [reloadToken])

  function updateWeight(mode: PricingMode, value: string) {
    setWeights((current) => ({ ...current, [mode]: value }))
    setFieldErrors((current) => ({ ...current, [mode]: undefined }))
  }

  function validateField(mode: PricingMode) {
    const { value, error } = parseWeight(weights[mode] ?? "")
    setFieldErrors((current) => ({
      ...current,
      [mode]: error ?? undefined,
    }))
    if (value === null) return
    const normalized = String(clampWeight(value))
    if (normalized !== (weights[mode] ?? "").trim()) {
      setWeights((current) => ({ ...current, [mode]: normalized }))
    }
  }

  function nudgeWeight(mode: PricingMode, delta: number) {
    updateWeight(mode, stepWeight(weights[mode] ?? "", delta))
  }

  function clearWeight(mode: PricingMode) {
    setWeights((current) => ({ ...current, [mode]: "" }))
    setFieldErrors((current) => ({ ...current, [mode]: undefined }))
  }

  async function save() {
    const payload: SuggestedPriceFormula[] = []
    const nextErrors: FieldErrors = {}
    let firstInvalidId: string | null = null

    for (const config of MODES) {
      const { value, error } = parseWeight(weights[config.mode] ?? "")
      if (error) {
        nextErrors[config.mode] = error
        firstInvalidId ??= config.id
      } else if (value !== null) {
        payload.push({ mode: config.mode, weight: value })
      }
    }

    if (firstInvalidId !== null) {
      setFieldErrors(nextErrors)
      document.getElementById(`weight-${firstInvalidId}`)?.focus()
      return
    }

    setBusy(true)
    setFieldErrors({})
    try {
      const data = await api.updateSettings({
        suggested_price_formulas: payload,
      })
      const next = inputsFromFormulas(data.suggested_price_formulas)
      setWeights(next)
      setSavedWeights(next)
      toast.success("وزن‌ها ذخیره شدند.")
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-24 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  if (loadError) {
    return (
      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="space-y-1">
          <p className="text-sm font-medium">دریافت تنظیمات ممکن نشد.</p>
          <p className="text-sm text-muted-foreground">{loadError}</p>
        </div>
        <Button
          variant="outline"
          onClick={() => setReloadToken((token) => token + 1)}
          className="h-11 shrink-0 sm:h-8"
        >
          <RefreshCw aria-hidden="true" />
          تلاش مجدد
        </Button>
      </div>
    )
  }

  const isDirty = MODES.some(
    (config) =>
      (weights[config.mode] ?? "").trim() !==
      (savedWeights[config.mode] ?? "").trim()
  )
  const configuredCount = MODES.filter(
    (config) => parseWeight(weights[config.mode] ?? "").value !== null
  ).length

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        if (!busy && isDirty) void save()
      }}
      className="flex flex-col gap-5"
    >
      <section className="rounded-2xl border border-border/70 bg-muted/30 p-4">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Info className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 space-y-1">
            <h3 className="text-sm font-semibold">
              قیمت پیشنهادی چطور ساخته می‌شود؟
            </h3>
            <p className="text-sm leading-6 text-muted-foreground">
              <span className="hidden sm:inline">
                هر کالا حالت قیمتگذاری خود را انتخاب می‌کند. حالت «قیمت رقیب» از
                ترکیب وزنی قیمت پایه پارسینا و قیمت رقیب دقیق استفاده می‌کند و
                حالت «محصول مشابه» تغییر روزانه قیمت محصول لینک‌شده را با همان
                وزن روی قیمت پایه اعمال می‌کند. وزن خالی یعنی برای آن حالت قیمت
                پیشنهادی نمایش داده نمی‌شود.
              </span>
              <span className="sm:hidden">
                قیمت رقیب: وزن رقیب؛ محصول مشابه: وزن تغییر روزانه. وزن خالی
                یعنی بدون قیمت پیشنهادی.
              </span>
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-border/70 bg-background px-4 py-3">
            <p className="text-xs font-medium text-muted-foreground">
              حالت «قیمت رقیب»
            </p>
            <p
              dir="ltr"
              className="mt-1 text-center font-mono text-sm font-medium tracking-tight text-foreground"
            >
              P = w × Pc + (1 − w) × Pb
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-background px-4 py-3">
            <p className="text-xs font-medium text-muted-foreground">
              حالت «محصول مشابه»
            </p>
            <p
              dir="ltr"
              className="mt-1 text-center font-mono text-sm font-medium tracking-tight text-foreground"
            >
              P = Pb × (1 + w × Δ)
            </p>
          </div>
        </div>
        <dl className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-4">
          <div className="flex items-center gap-2">
            <dt className="rounded-md bg-background px-1.5 py-0.5 font-mono text-[11px] text-foreground">
              w
            </dt>
            <dd>وزن رقیب یا تغییر روزانه (۰ تا ۱)</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="rounded-md bg-background px-1.5 py-0.5 font-mono text-[11px] text-foreground">
              Pc
            </dt>
            <dd>قیمت رقیب</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="rounded-md bg-background px-1.5 py-0.5 font-mono text-[11px] text-foreground">
              Δ
            </dt>
            <dd>درصد تغییر روزانه محصول لینک‌شده</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="rounded-md bg-background px-1.5 py-0.5 font-mono text-[11px] text-foreground">
              Pb
            </dt>
            <dd>قیمت پایه پارسینا</dd>
          </div>
        </dl>
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        {MODES.map((config) => {
          const parsed = parseWeight(weights[config.mode] ?? "")
          const weight = parsed.value
          const fieldError = fieldErrors[config.mode]
          const helpId = `weight-${config.id}-help`
          const errorId = `weight-${config.id}-error`
          const competitorShare =
            weight === null ? 0 : Math.min(Math.max(weight, 0), 1)
          const tracking = isTrackingMode(config.mode)
          return (
            <div
              key={config.mode}
              className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-background p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <label
                    htmlFor={`weight-${config.id}`}
                    className="text-sm font-semibold"
                  >
                    {config.label}
                  </label>
                  <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                    {config.hint}
                  </p>
                </div>
                <Badge
                  variant={weight === null ? "outline" : "secondary"}
                  className="shrink-0"
                >
                  {weight === null
                    ? "تنظیم نشده"
                    : `${formatPercent(weight)} ${tracking ? "تغییر" : "رقیب"}`}
                </Badge>
              </div>

              <div className="flex items-center gap-2">
                <div dir="ltr" className="relative flex-1">
                  <Input
                    id={`weight-${config.id}`}
                    type="number"
                    inputMode="decimal"
                    min={0}
                    max={1}
                    step={WEIGHT_STEP}
                    dir="ltr"
                    className="h-12 [appearance:textfield] px-12 text-center text-lg font-semibold tabular-nums [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    value={weights[config.mode] ?? ""}
                    onChange={(event) =>
                      updateWeight(config.mode, event.target.value)
                    }
                    onBlur={() => validateField(config.mode)}
                    onKeyDown={(event) => {
                      if (event.key === "ArrowUp") {
                        event.preventDefault()
                        nudgeWeight(config.mode, WEIGHT_STEP)
                      } else if (event.key === "ArrowDown") {
                        event.preventDefault()
                        nudgeWeight(config.mode, -WEIGHT_STEP)
                      }
                    }}
                    placeholder="0.6"
                    aria-label={
                      tracking
                        ? `وزن تغییر روزانه برای ${config.label}`
                        : `وزن قیمت رقیب برای ${config.label}`
                    }
                    aria-invalid={fieldError ? true : undefined}
                    aria-describedby={
                      fieldError ? `${helpId} ${errorId}` : helpId
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => nudgeWeight(config.mode, -WEIGHT_STEP)}
                    disabled={weight !== null && weight <= 0}
                    aria-label={`کاهش وزن ${config.label}`}
                    className="absolute inset-y-0 start-1 my-auto text-muted-foreground hover:text-foreground"
                  >
                    <Minus aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => nudgeWeight(config.mode, WEIGHT_STEP)}
                    disabled={weight !== null && weight >= 1}
                    aria-label={`افزایش وزن ${config.label}`}
                    className="absolute inset-y-0 end-1 my-auto text-muted-foreground hover:text-foreground"
                  >
                    <Plus aria-hidden="true" />
                  </Button>
                </div>
                {weight !== null ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => clearWeight(config.mode)}
                    aria-label={`پاک کردن وزن ${config.label}`}
                    className="shrink-0 text-muted-foreground hover:text-foreground"
                  >
                    <X aria-hidden="true" />
                  </Button>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <div
                  aria-hidden="true"
                  className="flex h-2 overflow-hidden rounded-full bg-muted"
                >
                  {weight === null ? null : (
                    <>
                      <span
                        className="bg-primary transition-[width]"
                        style={{ width: `${competitorShare * 100}%` }}
                      />
                      <span
                        className="bg-foreground/15 transition-[width]"
                        style={{ width: `${(1 - competitorShare) * 100}%` }}
                      />
                    </>
                  )}
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>
                    {tracking ? "تغییر روزانه" : "رقیب"}:{" "}
                    {weight === null ? "—" : formatPercent(competitorShare)}
                  </span>
                  <span>
                    پارسینا:{" "}
                    {weight === null ? "—" : formatPercent(1 - competitorShare)}
                  </span>
                </div>
              </div>

              <div className="space-y-1.5">
                <p id={helpId} className="text-[11px] text-muted-foreground">
                  بازه پیشنهادی: {config.range}
                </p>
                {weight !== null ? (
                  <p className="text-[11px] leading-5 text-muted-foreground">
                    {tracking
                      ? `فرمول: قیمت پایه × (۱ + ${formatWeight(weight)} × درصد تغییر روزانه)`
                      : `فرمول: ${formatWeight(weight)} × قیمت رقیب + ${formatWeight(1 - weight)} × قیمت پارسینا`}
                  </p>
                ) : null}
                {fieldError ? (
                  <p
                    id={errorId}
                    role="alert"
                    className="text-xs text-destructive"
                  >
                    {fieldError}
                  </p>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex flex-col gap-3 border-t border-border/70 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p
          className={`min-h-5 text-xs ${
            isDirty
              ? "text-amber-700 dark:text-amber-300"
              : "text-muted-foreground"
          }`}
        >
          {isDirty
            ? "تغییرات ذخیره نشده است."
            : configuredCount === 0
              ? "هنوز وزنی تنظیم نشده؛ ستون قیمت پیشنهادی خالی می‌ماند."
              : "وزن‌ها ذخیره شده‌اند."}
        </p>
        <Button
          type="submit"
          disabled={busy || !isDirty}
          aria-busy={busy}
          className="h-11 w-full sm:w-auto"
        >
          <BusyLabel
            busy={busy}
            idle="ذخیره"
            busyLabel={<span className="sr-only">در حال ذخیره…</span>}
            spinner
          />
        </Button>
      </div>
    </form>
  )
}
