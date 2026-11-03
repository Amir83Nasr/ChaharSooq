import { describe, expect, it } from "vitest"

import { formatPersianRelativeTime } from "./relative-time"

const NOW = Date.parse("2026-11-04T12:00:00Z")

describe("formatPersianRelativeTime", () => {
  it("says moments ago for recent and future moments", () => {
    expect(formatPersianRelativeTime(NOW - 10_000, NOW)).toBe("لحظاتی پیش")
    expect(formatPersianRelativeTime(NOW + 60_000, NOW)).toBe("لحظاتی پیش")
  })

  it("rounds minutes and hours the Persian way", () => {
    expect(formatPersianRelativeTime(NOW - 80_000, NOW)).toBe("یک دقیقه پیش")
    expect(formatPersianRelativeTime(NOW - 5 * 60_000, NOW)).toBe("۵ دقیقه پیش")
    expect(formatPersianRelativeTime(NOW - 80 * 60_000, NOW)).toBe(
      "یک ساعت پیش"
    )
    expect(formatPersianRelativeTime(NOW - 5 * 3_600_000, NOW)).toBe(
      "۵ ساعت پیش"
    )
  })

  it("names yesterday, counts older days, and gives up after a month", () => {
    expect(formatPersianRelativeTime(NOW - 26 * 3_600_000, NOW)).toBe("دیروز")
    expect(formatPersianRelativeTime(NOW - 3 * 86_400_000, NOW)).toBe(
      "۳ روز پیش"
    )
    expect(formatPersianRelativeTime(NOW - 40 * 86_400_000, NOW)).toBeNull()
    expect(formatPersianRelativeTime("not-a-date", NOW)).toBeNull()
  })
})
