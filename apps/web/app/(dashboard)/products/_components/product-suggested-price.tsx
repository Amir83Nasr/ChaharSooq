"use client"

import { useEffect, useState } from "react"

import { Price } from "@workspace/ui/persian/price"
import { formatPersianNumber } from "@workspace/ui/lib/number"
import { cn } from "@workspace/ui/lib/utils"

import { api, type ProductOut } from "@/lib/api"
import { competitorForRow } from "@/lib/competitor-price"
import { toTomanAmount } from "@/lib/money"
import {
  applyPriceBounds,
  suggestedPriceFor,
  suggestedPriceFromDailyChange,
  toSuggestedPriceWeights,
  type SuggestedPriceWeights,
} from "@/lib/suggested-price"

function formatPercent(value: number): string {
  const rounded = Math.round(value * 10) / 10
  const clean = Object.is(rounded, -0) ? 0 : rounded
  return `${clean > 0 ? "+" : clean < 0 ? "−" : ""}${formatPersianNumber(
    Math.abs(clean).toFixed(1).replace(/\.0$/, "")
  )}٪`
}

export function ProductSuggestedPrice({ product }: { product: ProductOut }) {
  const [weights, setWeights] = useState<SuggestedPriceWeights | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((settings) => {
        if (cancelled) return
        setWeights(toSuggestedPriceWeights(settings.suggested_price_formulas))
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const topGroup = product.top_group ?? "لوازم خانگی"
  // The formula follows the per-product mode; the category supplies the shared
  // weight and picks which similar-product store to display.
  const exact = product.pricing_mode === "exact_competitor"
  const noCompetitor = product.pricing_mode === "no_competitor_price"
  const weight = weights?.[topGroup] ?? null
  const fresh = product.competitor_prices.filter(
    (price) => price.is_fresh && price.price !== null
  )
  const competitor = exact
    ? competitorForRow(fresh, "best", topGroup)
    : (product.competitor_prices.find(
        (price) =>
          price.store === (topGroup === "مبلمان" ? "sofa" : "digifresh")
      ) ?? null)
  const amount = toTomanAmount(
    competitor?.price ?? null,
    competitor?.currency ?? null
  )
  const rawSuggested =
    !noCompetitor && competitor?.is_fresh === true
      ? exact
        ? suggestedPriceFor(product.price, amount, weight)
        : suggestedPriceFromDailyChange(
            product.price,
            competitor?.price_change_percent,
            weight
          )
      : null
  const suggested = applyPriceBounds(
    product.price,
    rawSuggested,
    product.allowed_decrease_percent,
    product.allowed_increase_percent
  )
  const changePercent =
    suggested !== null && product.price > 0
      ? ((suggested - product.price) / product.price) * 100
      : null

  const hint = error
    ? "دریافت تنظیمات ممکن نشد."
    : weights === null
      ? "در حال خواندن وزن‌ها…"
      : noCompetitor
        ? "این کالا فاقد قیمت رقیب است؛ قیمت پیشنهادی محاسبه نمی‌شود."
        : weight === null
          ? `برای دسته ${topGroup} وزنی ثبت نشده است.`
          : suggested === null
            ? exact
              ? "قیمت تازه‌ای از فروشگاه رقیب ثبت نشده است."
              : "برای محاسبه، لینک تازه و تغییر قیمت دو روز لازم است."
            : null

  return (
    <section className="rounded-2xl border border-border bg-card px-3 py-2.5 text-start">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
          <h3 className="shrink-0 text-xs font-medium text-muted-foreground">
            قیمت پیشنهادی
          </h3>
          {suggested !== null ? (
            <Price value={suggested} className="text-base font-bold" />
          ) : (
            <span className="text-sm text-muted-foreground">محاسبه نشد</span>
          )}
        </div>
        {changePercent !== null ? (
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
              changePercent > 0
                ? "bg-destructive/10 text-destructive"
                : changePercent < 0
                  ? "bg-success/10 text-success"
                  : "bg-muted text-muted-foreground"
            )}
          >
            {formatPercent(changePercent)} نسبت به قیمت فعلی
          </span>
        ) : null}
      </div>
      {hint ? (
        <p
          className={cn(
            "mt-1 text-[11px] leading-4",
            error ? "text-destructive" : "text-muted-foreground"
          )}
        >
          {hint}
        </p>
      ) : null}
    </section>
  )
}
