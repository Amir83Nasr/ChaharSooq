import { describe, expect, it } from "vitest"

import { formatToman } from "./currency"
import {
  formatPersianDate,
  formatPersianTime,
  formatPersianWeekday,
} from "./date"
import { DATE_SEP, THOUSAND_SEP } from "./locale"
import { formatPersianNumber, parsePriceFilterInput, toLatinDigits, toPersianDigits } from "./number"

describe("toPersianDigits", () => {
  it("converts latin digits", () => {
    expect(toPersianDigits("0123456789")).toBe("۰۱۲۳۴۵۶۷۸۹")
  })
})

describe("toLatinDigits", () => {
  it("converts persian and arabic digits", () => {
    expect(toLatinDigits("۰۱۲۳۴۵۶۷۸۹")).toBe("0123456789")
    expect(toLatinDigits("٠١٢٣٤٥٦٧٨٩")).toBe("0123456789")
    expect(toLatinDigits("۱۲٬۰۰۰")).toBe("12٬000")
  })
})

describe("formatPersianNumber", () => {
  it("groups with U+066C", () => {
    expect(formatPersianNumber(1000000)).toBe(
      `۱${THOUSAND_SEP}۰۰۰${THOUSAND_SEP}۰۰۰`
    )
  })

  it("never uses western comma", () => {
    expect(formatPersianNumber(1234567)).not.toContain(",")
  })

  it("round-trips through price filter parsing", () => {
    expect(parsePriceFilterInput("۱٬۰۰۰٬۰۰۰")).toBe("1000000")
    expect(parsePriceFilterInput("1000000")).toBe("1000000")
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
  it("emits persian digits without latin chars", () => {
    const out = formatPersianTime(new Date(2026, 9, 4, 9, 5, 7), true)
    expect(out).toBe("۰۹:۰۵:۰۷")
    expect(out).not.toMatch(/[0-9]/)
  })

  it("omits seconds by default", () => {
    expect(formatPersianTime(new Date(2026, 9, 4, 9, 5, 7))).toBe("۰۹:۰۵")
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
