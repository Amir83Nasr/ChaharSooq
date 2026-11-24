import type { CompetitorCurrency } from "./api"

// This is the frontend's only currency conversion. It is NOT for Parsina data:
// the backend divides Parsina rials by 10 at ingestion, so every product price,
// cardex amount and API payload reaching the UI is already Toman. It exists
// solely for competitor listings, whose payload carries an explicit currency:
// only IRR values are divided here, IRT (and Toman product prices) pass through.

export function toTomanAmount(
  price: number | null | undefined,
  currency: CompetitorCurrency | string | null | undefined
): number | null {
  if (price === null || price === undefined) return null
  if (currency === "IRR") return Math.round(price / 10)
  return price
}
