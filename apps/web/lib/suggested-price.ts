import type { SuggestedPriceFormula, TopGroup } from "./api"

/** Competitor weight per top group — absent means "not configured". */
export type SuggestedPriceWeights = Partial<Record<TopGroup, number>>

export function toSuggestedPriceWeights(
  formulas: SuggestedPriceFormula[]
): SuggestedPriceWeights {
  const weights: SuggestedPriceWeights = {}
  for (const formula of formulas) {
    if (
      Number.isFinite(formula.weight) &&
      formula.weight >= 0 &&
      formula.weight <= 1
    ) {
      weights[formula.top_group] = formula.weight
    }
  }
  return weights
}

/**
 * Weighted blend of the Parsina base price and the competitor price:
 * `weight × competitor + (1 − weight) × base`.
 *
 * With a weight inside [0, 1] the result already sits between the two
 * source prices; the clamp keeps it there even if upstream data misbehaves.
 * Missing base/competitor/weight means there is nothing to suggest yet.
 */
export function suggestedPriceFor(
  basePrice: number,
  competitorPrice: number | null | undefined,
  weight: number | null | undefined
): number | null {
  if (competitorPrice === null || competitorPrice === undefined) return null
  if (!Number.isFinite(basePrice) || basePrice <= 0) return null
  if (!Number.isFinite(competitorPrice) || competitorPrice <= 0) return null
  if (weight === null || weight === undefined) return null
  if (!Number.isFinite(weight) || weight < 0 || weight > 1) return null
  const blended = weight * competitorPrice + (1 - weight) * basePrice
  const low = Math.min(basePrice, competitorPrice)
  const high = Math.max(basePrice, competitorPrice)
  return Math.round(Math.min(Math.max(blended, low), high))
}

/**
 * Furniture/carpet formula: the linked Sofa/DigiFresh product has no direct
 * competitor price to blend. Its daily price change replaces `Pc`:
 * `P = Pb × (1 + w × Δ)`, where `Δ` is the daily change in percent.
 */
export function suggestedPriceFromDailyChange(
  basePrice: number,
  changePercent: number | null | undefined,
  weight: number | null | undefined
): number | null {
  if (changePercent === null || changePercent === undefined) return null
  if (!Number.isFinite(basePrice) || basePrice <= 0) return null
  if (!Number.isFinite(changePercent)) return null
  if (weight === null || weight === undefined) return null
  if (!Number.isFinite(weight) || weight < 0 || weight > 1) return null
  const value = basePrice * (1 + (weight * changePercent) / 100)
  return Math.round(Math.max(value, 0))
}

/**
 * Per-product clamp around the Parsina base price:
 * `floor = Pb × (1 − m)` and `ceiling = Pb × (1 + n)`.
 * `null`/invalid percentages disable that side.
 */
export function applyPriceBounds(
  basePrice: number,
  suggestedPrice: number | null,
  allowedDecreasePercent: number | null | undefined,
  allowedIncreasePercent: number | null | undefined
): number | null {
  if (suggestedPrice === null || !Number.isFinite(suggestedPrice)) return null
  if (!Number.isFinite(basePrice) || basePrice <= 0) return suggestedPrice
  const decrease =
    allowedDecreasePercent !== null &&
    allowedDecreasePercent !== undefined &&
    Number.isFinite(allowedDecreasePercent) &&
    allowedDecreasePercent >= 0
      ? allowedDecreasePercent
      : null
  const increase =
    allowedIncreasePercent !== null &&
    allowedIncreasePercent !== undefined &&
    Number.isFinite(allowedIncreasePercent) &&
    allowedIncreasePercent >= 0
      ? allowedIncreasePercent
      : null
  const floor = decrease === null ? -Infinity : basePrice * (1 - decrease / 100)
  const ceiling =
    increase === null ? Infinity : basePrice * (1 + increase / 100)
  return Math.round(Math.min(Math.max(suggestedPrice, floor), ceiling))
}
