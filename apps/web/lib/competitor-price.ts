/** Which competitor price a catalog row shows, and how it is picked. */

import type {
  CompetitorPrice,
  CompetitorStore,
  PricingMode,
  TopGroup,
} from "./api-types"
import { toTomanAmount } from "./money"
import { storesForTopGroup } from "./top-groups"

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

/**
 * Stores relevant for a competitor market. The section owns the link slots;
 * the per-product mode only decides how those prices feed the suggestion.
 */
function trackedStores(
  market: CompetitorMarket,
  top: TopGroup | null
): readonly CompetitorStore[] {
  const sectionStores = storesForTopGroup(top)
  if (market === "best") return sectionStores
  return sectionStores.includes(market as CompetitorStore)
    ? [market as CompetitorStore]
    : []
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

// ── EMPTY-CELL MESSAGES ────────────────────────────────────────────────

/**
 * Short label for a competitor-derived cell with no value. The long reason
 * goes into the cell's `title` tooltip so the column stays narrow.
 */
export function competitorEmptyMessage(
  mode: PricingMode,
  kind: "price" | "diff" | "daily_change" | "suggested"
): string {
  if (mode === "similar_product" && kind === "price") return "کالای مشابه"
  if (kind === "price" || kind === "diff") return "—"
  return "داده کافی نیست"
}

/** Detailed reason for the tooltip, where space is not constrained. */
export function competitorEmptyHint(
  mode: PricingMode,
  kind: "daily_change" | "suggested"
): string {
  if (mode === "similar_product") {
    return kind === "daily_change"
      ? "برای تغییر روزانه، مشاهدهٔ قیمت دو روز لازم است"
      : "برای محاسبهٔ قیمت، تغییر قیمت دو روز لازم است"
  }
  return kind === "daily_change"
    ? "برای تغییر روزانه، مشاهدهٔ قیمت دو روز لازم است"
    : "برای محاسبهٔ قیمت، قیمت تازه لازم است"
}
