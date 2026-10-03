import { DATE_SEP, FA_DIGITS, THOUSAND_SEP } from "./locale"

const LATIN_DIGIT_RE = /[0-9]/g

export function toPersianDigits(value: string | number | bigint): string {
  return String(value).replace(LATIN_DIGIT_RE, (d) => FA_DIGITS[Number(d)] ?? d)
}

function groupThousands(digits: string): string {
  const clean = digits.replace(/[^0-9]/g, "") || "0"
  return clean.replace(/\B(?=(\d{3})+(?!\d))/g, THOUSAND_SEP)
}

/** Machine value in, Persian display string out. Never persist the result. */
export function formatPersianNumber(value: number | string | bigint): string {
  const raw = String(value).trim()
  const sign = raw.startsWith("-") ? "-" : ""
  const unsigned = sign ? raw.slice(1) : raw
  const [int = "", frac] = unsigned.split(".")
  const grouped = groupThousands(int)
  const ascii =
    frac !== undefined ? `${grouped}.${frac.replace(/[^0-9]/g, "")}` : grouped
  return toPersianDigits(`${sign}${ascii}`).replace(".", DATE_SEP)
}
