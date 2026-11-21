/** Which competitor price a catalog row shows, and how it is picked. */

import type {
  CompetitorPrice,
  CompetitorStore,
  DefaultCompetitorStore,
  TopGroup,
} from "./api-types"
import { toTomanAmount } from "./money"
import { comparesWithCompetitor } from "./top-groups"

export type CompetitorMarket = CompetitorStore | "best"

export const STORE_MARKET_LABELS: Record<CompetitorMarket, string> = {
  best: "ارزانترین رقیب",
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
  sofa: "سوفا",
  digifresh: "دیجی‌فرش",
  other: "دیگر",
}

/** Markets offered by the products toolbar / settings (the two direct rivals). */
export const COMPETITOR_MARKETS: {
  store: DefaultCompetitorStore
  label: string
}[] = [
  { store: "best", label: STORE_MARKET_LABELS.best },
  { store: "digikala", label: STORE_MARKET_LABELS.digikala },
  { store: "technolife", label: STORE_MARKET_LABELS.technolife },
]

const DIRECT_STORES: readonly CompetitorStore[] = ["digikala", "technolife"]

function trackedStores(
  market: CompetitorMarket,
  top: TopGroup | null
): readonly CompetitorStore[] {
  if (comparesWithCompetitor(top) || top === null) {
    if (market === "best") return DIRECT_STORES
    return market === "digikala" || market === "technolife" ? [market] : []
  }
  if (top === "مبلمان")
    return market === "best" || market === "sofa" ? ["sofa"] : []
  if (top === "فرش") {
    return market === "best" || market === "digifresh" ? ["digifresh"] : []
  }
  return []
}

/** Whether the competitor column has anything to show for this row. */
export function showsCompetitorPrice(
  market: CompetitorMarket,
  top: TopGroup | null
): boolean {
  return trackedStores(market, top).length > 0
}

function amountOf(price: CompetitorPrice): number | null {
  return toTomanAmount(price.price, price.currency)
}

/**
 * Pick the price to display. Explicit markets keep only their own listing;
 * `best` uses the only available listing, or the cheaper one when both exist.
 * A listing without a price never wins over one that has a price.
 */
export function competitorForRow(
  prices: readonly CompetitorPrice[],
  market: CompetitorMarket,
  top: TopGroup | null
): CompetitorPrice | null {
  const stores = trackedStores(market, top)
  const candidates = prices.filter((price) => stores.includes(price.store))
  if (market !== "best") return candidates[0] ?? null

  const priced = candidates.filter((price) => amountOf(price) !== null)
  if (priced.length === 0) return candidates[0] ?? null
  return priced.reduce((cheapest, price) =>
    (amountOf(price) ?? 0) < (amountOf(cheapest) ?? 0) ? price : cheapest
  )
}
