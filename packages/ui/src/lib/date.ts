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
  return `${formatPersianDate(date)}، ساعت ${formatPersianTime(date)}`
}

/** Machine value in, `۱۲:۳۴`-style Persian-digit time out. */
export function formatPersianTime(
  value: Date | string | number,
  withSeconds = false
): string {
  const date = value instanceof Date ? value : new Date(value)
  const base = `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
  return toPersianDigits(
    withSeconds ? `${base}:${pad2(date.getSeconds())}` : base
  )
}

const weekdayFormatter = new Intl.DateTimeFormat("fa-IR", { weekday: "long" })

/** Machine value in, Persian weekday name out (e.g. `یکشنبه`). */
export function formatPersianWeekday(value: Date | string | number): string {
  const date = value instanceof Date ? value : new Date(value)
  return weekdayFormatter.format(date)
}
