import { formatPersianNumber } from "./number"

/** Toman source stays numeric; glyph rendered by <Price/>, not this string. */
export function formatToman(value: number | bigint): string {
  return formatPersianNumber(value)
}
