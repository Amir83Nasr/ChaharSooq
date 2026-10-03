import { toJalaliParts } from "./jalali"
import { DATE_SEP } from "./locale"
import { toPersianDigits } from "./number"

const pad2 = (n: number) => String(n).padStart(2, "0")

/** Machine value in, `۱۴۰۵٫۰۵٫۰۵`-style string out. Never persist the result. */
export function formatPersianDate(value: Date | string | number): string {
  const { year, month, day } = toJalaliParts(value)
  return toPersianDigits(
    `${year}${DATE_SEP}${pad2(month)}${DATE_SEP}${pad2(day)}`
  )
}

export function formatPersianDateTime(value: Date | string | number): string {
  const date = value instanceof Date ? value : new Date(value)
  const time = toPersianDigits(
    `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
  )
  return `${formatPersianDate(date)}، ساعت ${time}`
}
