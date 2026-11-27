import { DATE_SEP } from "./locale"
import { toPersianDigits } from "./number"

export interface JalaliParts {
  year: number
  month: number
  day: number
}

const partsFormatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian-nu-latn", {
  year: "numeric",
  month: "numeric",
  day: "numeric",
})

// Calendar arithmetic always reads UTC days: a viewer's time zone may never
// shift the day a user picked in the grid.
const utcPartsFormatter = new Intl.DateTimeFormat(
  "fa-IR-u-ca-persian-nu-latn",
  {
    timeZone: "UTC",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }
)

const DAY_MS = 86_400_000

// Days elapsed before each Jalali month starts; month 12 is completed below.
const MONTH_START_DAYS = [0, 31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336]
const ESFAND_START_DAYS = 336

export const JALALI_MONTH_NAMES = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
] as const

/** Saturday-first weekday initials, matching the Persian week. */
export const JALALI_WEEKDAY_INITIALS = [
  "ش",
  "ی",
  "د",
  "س",
  "چ",
  "پ",
  "ج",
] as const

function readParts(formatter: Intl.DateTimeFormat, value: Date): JalaliParts {
  const parts = formatter.formatToParts(value)
  const get = (type: string) =>
    Number(parts.find((part) => part.type === type)?.value ?? NaN)
  return { year: get("year"), month: get("month"), day: get("day") }
}

/** Gregorian/machine value in, Jalali parts out (display time zone). */
export function toJalaliParts(value: Date | string | number): JalaliParts {
  const date = value instanceof Date ? value : new Date(value)
  return readParts(partsFormatter, date)
}

/** Gregorian/machine value in, Jalali parts out in UTC (calendar math). */
export function toJalaliPartsUtc(value: Date): JalaliParts {
  return readParts(utcPartsFormatter, value)
}

export function compareJalaliParts(a: JalaliParts, b: JalaliParts): number {
  if (a.year !== b.year) return a.year - b.year
  if (a.month !== b.month) return a.month - b.month
  return a.day - b.day
}

function jalaliDayOfYear({ month, day }: JalaliParts): number {
  return (MONTH_START_DAYS[month - 1] ?? 0) + day - 1
}

/**
 * First day of a Jalali year as a UTC timestamp at midnight.
 * Nowruz falls on March 20 or 21, so a short scan around it is enough.
 */
function startOfJalaliYearUtc(year: number): number {
  const base = Date.UTC(year + 621, 2, 19)
  for (let offset = 0; offset < 5; offset += 1) {
    const candidate = base + offset * DAY_MS
    const parts = toJalaliPartsUtc(new Date(candidate))
    if (parts.year === year && parts.month === 1 && parts.day === 1) {
      return candidate
    }
  }
  throw new RangeError(`Could not resolve the start of Jalali year ${year}`)
}

/** Jalali parts in, UTC midnight of that Gregorian day out. */
export function fromJalaliParts(parts: JalaliParts): Date {
  return new Date(
    startOfJalaliYearUtc(parts.year) + jalaliDayOfYear(parts) * DAY_MS
  )
}

export function jalaliMonthLength(year: number, month: number): number {
  if (month <= 6) return 31
  if (month <= 11) return 30
  const yearStart = startOfJalaliYearUtc(year)
  const nextStart = startOfJalaliYearUtc(year + 1)
  return Math.round((nextStart - yearStart) / DAY_MS) - ESFAND_START_DAYS
}

/** Shift a year/month pair by whole Jalali months. */
export function shiftJalaliMonth(
  parts: Pick<JalaliParts, "year" | "month">,
  delta: number
): Pick<JalaliParts, "year" | "month"> {
  const index = parts.year * 12 + (parts.month - 1) + delta
  return { year: Math.floor(index / 12), month: (index % 12) + 1 }
}

/** Shift by whole Jalali months, clamping the day to the target month. */
export function addJalaliMonths(
  parts: JalaliParts,
  delta: number
): JalaliParts {
  const { year, month } = shiftJalaliMonth(parts, delta)
  return {
    year,
    month,
    day: Math.min(parts.day, jalaliMonthLength(year, month)),
  }
}

/** Saturday = 0 … Friday = 6, independent of the display time zone. */
export function jalaliWeekdayIndex(parts: JalaliParts): number {
  const day = fromJalaliParts(parts)
  return (day.getUTCDay() + 1) % 7
}

/** One month padded to whole Saturday-first weeks; `null` fills the edges. */
export function buildJalaliMonth(parts: {
  year: number
  month: number
}): (JalaliParts | null)[] {
  const length = jalaliMonthLength(parts.year, parts.month)
  const leading = jalaliWeekdayIndex({
    year: parts.year,
    month: parts.month,
    day: 1,
  })
  const days: (JalaliParts | null)[] = Array.from(
    { length: leading },
    () => null
  )
  for (let day = 1; day <= length; day += 1) {
    days.push({ year: parts.year, month: parts.month, day })
  }
  while (days.length % 7 !== 0) days.push(null)
  return days
}

/** Jalali parts in, `۱۴۰۵٫۰۵٫۰۵`-style display string out. */
export function formatJalaliParts({ year, month, day }: JalaliParts): string {
  const pad2 = (value: number) => String(value).padStart(2, "0")
  return toPersianDigits(
    `${year}${DATE_SEP}${pad2(month)}${DATE_SEP}${pad2(day)}`
  )
}

/** Jalali day in, Gregorian ISO day (`YYYY-MM-DD`) for machine values. */
export function jalaliPartsToIsoDay(parts: JalaliParts): string {
  return fromJalaliParts(parts).toISOString().slice(0, 10)
}

/** Inclusive number of days between two Jalali days (same day = 1). */
export function jalaliDaySpan(from: JalaliParts, to: JalaliParts): number {
  const days = Math.round(
    (fromJalaliParts(to).getTime() - fromJalaliParts(from).getTime()) / DAY_MS
  )
  return Math.abs(days) + 1
}
