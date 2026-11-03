import { formatPersianNumber } from "./number"

const SECOND_MS = 1000
const MINUTE_MS = 60 * SECOND_MS
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

/** Machine value in, Persian relative string out (`۵ دقیقه پیش`).
 * Returns null when the moment is 30+ days away (or unparseable) so callers
 * can fall back to an absolute date. Never persist the result. */
export function formatPersianRelativeTime(
  value: Date | string | number,
  now: Date | number = Date.now()
): string | null {
  const then =
    value instanceof Date ? value.getTime() : new Date(value).getTime()
  if (Number.isNaN(then)) return null
  const base = now instanceof Date ? now.getTime() : now
  const seconds = Math.floor((base - then) / SECOND_MS)
  if (seconds < 45) return "لحظاتی پیش"
  if (seconds < 90) return "یک دقیقه پیش"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 45) return `${formatPersianNumber(minutes)} دقیقه پیش`
  if (minutes < 90) return "یک ساعت پیش"
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${formatPersianNumber(hours)} ساعت پیش`
  const days = Math.floor(hours / 24)
  if (days < 1) return "لحظاتی پیش"
  if (days < 2) return "دیروز"
  if (days < 30) return `${formatPersianNumber(days)} روز پیش`
  return null
}
