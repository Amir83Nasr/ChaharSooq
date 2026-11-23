/** Which competitor price a catalog row shows, and how it is picked. */

import type { CompetitorPrice, CompetitorStore, TopGroup } from "./api-types"
import { toTomanAmount } from "./money"
import { comparesWithCompetitor } from "./top-groups"

export type CompetitorMarket = CompetitorStore | "best"

/** Markets offered by the products toolbar (the cheapest option plus direct rivals). */
export type CompetitorMarketOption =
  "best" | "digikala" | "technolife" | "torob"

export const STORE_MARKET_LABELS: Record<CompetitorMarket, string> = {
  best: "ارزانترین رقیب",
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
  sofa: "سوفا",
  torob: "ترب",
  digifresh: "دیجی‌فرش",
  other: "دیگر",
}

/** Markets offered by the products toolbar. */
export const COMPETITOR_MARKETS: {
  store: CompetitorMarketOption
  label: string
}[] = [
  { store: "best", label: STORE_MARKET_LABELS.best },
  { store: "digikala", label: STORE_MARKET_LABELS.digikala },
  { store: "technolife", label: STORE_MARKET_LABELS.technolife },
  { store: "torob", label: STORE_MARKET_LABELS.torob },
]

const DIRECT_STORES: readonly CompetitorStore[] = [
  "digikala",
  "technolife",
  "torob",
]

/**
 * Stores shown for a competitor market. The exact-vs-similar decision is no
 * longer made here: it comes from `product.pricing_mode`. This helper only
 * picks which similar-product store to display for a catalog section.
 */
function trackedStores(
  market: CompetitorMarket,
  top: TopGroup | null
): readonly CompetitorStore[] {
  if (comparesWithCompetitor(top) || top === null) {
    if (market === "best") return DIRECT_STORES
    return DIRECT_STORES.includes(market as CompetitorStore)
      ? [market as CompetitorStore]
      : []
  }
  if (top === "مبلمان") {
    if (market === "best" || market === "sofa") return ["sofa", "torob"]
    return market === "torob" ? ["torob"] : []
  }
  if (top === "فرش") {
    if (market === "best" || market === "digifresh")
      return ["digifresh", "torob"]
    return market === "torob" ? ["torob"] : []
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
