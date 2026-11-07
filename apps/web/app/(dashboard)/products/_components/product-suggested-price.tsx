"use client"

import { useEffect, useState } from "react"

import { Price } from "@workspace/ui/persian/price"
import { formatPersianNumber } from "@workspace/ui/lib/number"

import { api, type ProductOut, type TopGroup } from "@/lib/api"
import { toTomanAmount } from "@/lib/money"
import {
  applyPriceBounds,
  suggestedPriceFor,
  suggestedPriceFromDailyChange,
  toSuggestedPriceWeights,
  type SuggestedPriceWeights,
} from "@/lib/suggested-price"

function topGroupOf(name: string | null): TopGroup {
  const value = name?.trim() ?? ""
  if (value.startsWith("فرش")) return "فرش"
  if (value.startsWith("مبلمان")) return "مبلمان"
  return "لوازم خانگی"
}

function formatPercent(value: number): string {
  const rounded = Math.round(value * 10) / 10
  const clean = Object.is(rounded, -0) ? 0 : rounded
  return `${clean > 0 ? "+" : clean < 0 ? "−" : ""}${formatPersianNumber(
    Math.abs(clean).toFixed(1).replace(/\.0$/, "")
  )}٪`
}

export function ProductSuggestedPrice({ product }: { product: ProductOut }) {
  const [weights, setWeights] = useState<SuggestedPriceWeights | null>(null)
  const [defaultStore, setDefaultStore] = useState<"digikala" | "technolife">(
    "digikala"
  )
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((settings) => {
        if (cancelled) return
        setWeights(toSuggestedPriceWeights(settings.suggested_price_formulas))
        setDefaultStore(settings.default_competitor_store)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const topGroup = topGroupOf(product.main_group_name)
  const tracking = topGroup !== "لوازم خانگی"
  const weight = weights?.[topGroup] ?? null
  const fresh = product.competitor_prices.filter(
    (price) => price.is_fresh && price.price !== null
  )
  const competitor = tracking
    ? (product.competitor_prices.find(
        (price) =>
          price.store === (topGroup === "مبلمان" ? "sofa" : "digifresh")
      ) ?? null)
    : (fresh.find((price) => price.store === defaultStore) ?? fresh[0] ?? null)
  const amount = toTomanAmount(
    competitor?.price ?? null,
    competitor?.currency ?? null
  )
  const rawSuggested =
    competitor?.is_fresh === true
      ? tracking
        ? suggestedPriceFromDailyChange(
            product.price,
            competitor?.price_change_percent,
            weight
          )
        : suggestedPriceFor(product.price, amount, weight)
      : null
  const suggested = applyPriceBounds(
    product.price,
    rawSuggested,
    product.allowed_decrease_percent,
    product.allowed_increase_percent
  )

  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card p-4 text-start">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">قیمت پیشنهادی</h3>
          <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
            {tracking
              ? "بر پایه قیمت پایه و تغییر روزانه محصول لینک‌شده"
              : "ترکیب وزنی قیمت پایه و تازه‌ترین قیمت رقیب"}
          </p>
        </div>
        {suggested !== null ? (
          <Price value={suggested} className="text-lg font-bold" />
        ) : (
          <span className="text-sm text-muted-foreground">محاسبه نشد</span>
        )}
      </div>

      {error ? (
        <p className="text-xs text-destructive">دریافت تنظیمات ممکن نشد.</p>
      ) : weights === null ? (
        <p className="text-xs text-muted-foreground">در حال خواندن وزن‌ها…</p>
      ) : weight === null ? (
        <p className="text-xs text-muted-foreground">
          برای گروه {topGroup} وزنی در تنظیمات قیمت‌گذاری ثبت نشده است.
        </p>
      ) : suggested === null ? (
        <p className="text-xs text-muted-foreground">
          {tracking
            ? "برای این کالا لینک تازه و تغییر قیمت دو روز لازم است."
            : "برای این کالا قیمت تازه‌ای از فروشگاه رقیب ثبت نشده است."}
        </p>
      ) : (
        <div className="space-y-1.5 rounded-xl bg-muted/50 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
          {tracking ? (
            <p dir="ltr" className="text-center font-mono">
              P = Pb × (1 + {formatPersianNumber(weight)} ×{" "}
              {competitor?.price_change_percent !== null &&
              competitor?.price_change_percent !== undefined
                ? formatPercent(competitor.price_change_percent)
                : "Δ"}
              )
            </p>
          ) : (
            <p dir="ltr" className="text-center font-mono">
              P = {formatPersianNumber(weight)} × Pc +{" "}
              {formatPersianNumber(1 - weight)} × Pb
            </p>
          )}
          <p>
            کف مجاز:{" "}
            {product.allowed_decrease_percent === null ? (
              "بدون محدودیت"
            ) : (
              <Price
                value={Math.round(
                  product.price * (1 - product.allowed_decrease_percent / 100)
                )}
              />
            )}{" "}
            · سقف مجاز:{" "}
            {product.allowed_increase_percent === null ? (
              "بدون محدودیت"
            ) : (
              <Price
                value={Math.round(
                  product.price * (1 + product.allowed_increase_percent / 100)
                )}
              />
            )}
          </p>
        </div>
      )}
    </section>
  )
}
