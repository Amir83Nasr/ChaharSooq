import type { TopGroup } from "./api-types"

/**
 * Catalog sections in display order — mirrors the backend
 * `app/core/top_groups.py`. Filters, table cells, and suggested prices all
 * read the section from here so a new division is one edit, not five.
 */
export const TOP_GROUPS: readonly TopGroup[] = [
  "فرش",
  "مبلمان",
  "لوازم خانگی",
  "کالای دیجیتال",
]

/** Parsina main groups that belong to کالای دیجیتال. */
const DIGITAL_GROUP_PREFIXES = [
  "کنسول بازی",
  "گوشی و تبلت",
  "لبت تاب", // Parsina's spelling; «لپ تاپ» is the common one.
  "لپ تاپ",
] as const

export function isDigitalGroup(name: string | null): boolean {
  const value = name?.trim() ?? ""
  return DIGITAL_GROUP_PREFIXES.some((prefix) => value.startsWith(prefix))
}

export function isTopGroup(value: string | null): value is TopGroup {
  return value !== null && (TOP_GROUPS as readonly string[]).includes(value)
}

/** Section (بخش) of one raw Parsina group; `null` when it has no group. */
export function topGroupOf(name: string | null): TopGroup | null {
  const value = name?.trim() ?? ""
  if (!value) return null
  if (isDigitalGroup(value)) return "کالای دیجیتال"
  if (value.startsWith("فرش")) return "فرش"
  if (value.startsWith("مبلمان")) return "مبلمان"
  return "لوازم خانگی"
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
 * Direct competitor sections: a fresh Digikala/Technolife price is blended
 * into the suggested price. Carpet/furniture instead track a linked product's
 * daily change.
 */
export function comparesWithCompetitor(top: TopGroup | null): boolean {
  return top === "لوازم خانگی" || top === "کالای دیجیتال"
}
