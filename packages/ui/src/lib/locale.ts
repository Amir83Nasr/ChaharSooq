export const FA_DIGITS = [
  "۰",
  "۱",
  "۲",
  "۳",
  "۴",
  "۵",
  "۶",
  "۷",
  "۸",
  "۹",
] as const

/** U+066C ARABIC THOUSANDS SEPARATOR — required grouping mark. */
export const THOUSAND_SEP = "٬"

/** U+066B ARABIC DECIMAL SEPARATOR — required date separator. */
export const DATE_SEP = "٫"

/** Decimal separator for fractional numbers (U+066B). Kept separate from
 * DATE_SEP so date formatting never drifts when decimals change. */
export const DECIMAL_SEP = "٫"
