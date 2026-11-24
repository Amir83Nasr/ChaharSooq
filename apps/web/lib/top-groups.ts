import type { CompetitorStore, TopGroup } from "./api-types"

/**
 * Catalog sections in display order. The section itself is computed once by
 * the backend and sent as `ProductOut.top_group`; this module only holds
 * presentation helpers (labels, brand display, competitor rules).
 */
export const TOP_GROUPS: readonly TopGroup[] = [
  "کالای دیجیتال",
  "لوازم خانگی",
  "فرش",
  "مبلمان",
]

export function isTopGroup(value: string | null): value is TopGroup {
  return value !== null && (TOP_GROUPS as readonly string[]).includes(value)
}

/**
 * Display brand — the remainder after the section prefix. Digital groups have
 * no brand prefix, so the group name itself is the brand.
 */
export function brandOf(
  name: string | null,
  top: TopGroup | null
): string | null {
  if (!name) return null
  const value = name.trim()
  if (!value) return null
  if (top === "فرش") {
    const rest = value.replace(/^فرش\s*/, "").trim()
    return rest || null
  }
  if (top === "مبلمان") {
    const rest = value.replace(/^مبلمان\s*/, "").trim()
    return rest || null
  }
  if (top === "لوازم خانگی") {
    const rest = value.replace(/^لوازم\s+خان[گک]ی\s*/, "").trim()
    return rest || value
  }
  return value
}

/**
 * Competitor link slots for a catalog section — the single source of truth for
 * the detail dialog. The links are the same for both active pricing modes; only
 * the suggested-price formula differs. There is no manual «other» store.
 */
export const STORES_BY_TOP_GROUP: Readonly<
  Record<TopGroup, readonly CompetitorStore[]>
> = {
  "کالای دیجیتال": ["digikala", "technolife", "torob"],
  "لوازم خانگی": ["digikala", "technolife", "torob"],
  فرش: ["digifresh", "torob"],
  مبلمان: ["sofa", "torob"],
}

/** Link slots for one product; rows without a group behave like appliances. */
export function storesForTopGroup(
  top: TopGroup | null
): readonly CompetitorStore[] {
  return STORES_BY_TOP_GROUP[top ?? "لوازم خانگی"]
}

/**
 * Legacy display hint: the sections that historically blended a direct
 * competitor price. Kept for display/branding; the formula itself is selected
 * per product through `ProductOut.pricing_mode`.
 */
export function comparesWithCompetitor(top: TopGroup | null): boolean {
  return top === "لوازم خانگی" || top === "کالای دیجیتال"
}
