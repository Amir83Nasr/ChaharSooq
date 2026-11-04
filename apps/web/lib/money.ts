import type { CompetitorCurrency } from "./api"

/** IRR (ریال) → تومان for display/comparison. IRT passes through. */
export function toTomanAmount(
  price: number | null | undefined,
  currency: CompetitorCurrency | string | null | undefined
): number | null {
  if (price === null || price === undefined) return null
  if (currency === "IRR") return Math.round(price / 10)
  return price
}
