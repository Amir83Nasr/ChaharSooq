import { describe, expect, it } from "vitest"

import { formatToman } from "./currency"
import {
  formatPersianDate,
  formatPersianTime,
  formatPersianWeekday,
} from "./date"
import { DATE_SEP, THOUSAND_SEP } from "./locale"
import {
  formatPersianNumber,
  parsePriceFilterInput,
  toLatinDigits,
  toPersianDigits,
} from "./number"

describe("digits", () => {
  it("converts latin/persian/arabic digits both ways", () => {
    expect(toPersianDigits("0123456789")).toBe("۰۱۲۳۴۵۶۷۸۹")
    expect(toLatinDigits("۰۱۲۳۴۵۶۷۸۹")).toBe("0123456789")
    expect(toLatinDigits("٠١٢٣٤٥٦٧٨٩")).toBe("0123456789")
    expect(toLatinDigits("۱۲٬۰۰۰")).toBe("12٬000")
  })
})

describe("formatPersianNumber", () => {
  it("groups with U+066C, never a western comma, and round-trips filters", () => {
    expect(formatPersianNumber(1000000)).toBe(
      `۱${THOUSAND_SEP}۰۰۰${THOUSAND_SEP}۰۰۰`
    )
    expect(formatPersianNumber(1234567)).not.toContain(",")
    expect(parsePriceFilterInput("۱٬۰۰۰٬۰۰۰")).toBe("1000000")
    expect(parsePriceFilterInput(formatPersianNumber(250000))).toBe("250000")
  })
})

describe("formatToman", () => {
  it("matches grouped persian output", () => {
    expect(formatToman(1000000)).toBe(formatPersianNumber(1000000))
  })
})

describe("formatPersianDate", () => {
  it("uses Jalali with U+066B separators", () => {
    const out = formatPersianDate(new Date(2026, 9, 4))
    expect(out).toContain(DATE_SEP)
    expect(out).not.toMatch(/[/.,-]/)
    expect(out).toMatch(
      new RegExp(`^[۰-۹]+${DATE_SEP}[۰-۹]{2}${DATE_SEP}[۰-۹]{2}$`)
    )
  })
})

describe("formatPersianTime", () => {
  it("emits persian digits with optional seconds", () => {
    expect(formatPersianTime(new Date(2026, 9, 4, 9, 5, 7), true)).toBe(
      "۰۹:۰۵:۰۷"
    )
    expect(formatPersianTime(new Date(2026, 9, 4, 9, 5, 7))).toBe("۰۹:۰۵")
    expect(formatPersianTime(new Date(2026, 9, 4, 9, 5, 7), true)).not.toMatch(
      /[0-9]/
    )
  })
})

describe("formatPersianWeekday", () => {
  it("matches Intl fa-IR weekday", () => {
    const date = new Date(2026, 9, 4)
    expect(formatPersianWeekday(date)).toBe(
      new Intl.DateTimeFormat("fa-IR", { weekday: "long" }).format(date)
    )
  })
})
