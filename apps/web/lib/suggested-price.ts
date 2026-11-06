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
