import { describe, expect, it } from "vitest"

import { formatToman } from "./currency"
import { formatPersianDate } from "./date"
import { DATE_SEP, THOUSAND_SEP } from "./locale"
import { formatPersianNumber, toPersianDigits } from "./number"

describe("toPersianDigits", () => {
  it("converts latin digits", () => {
    expect(toPersianDigits("0123456789")).toBe("۰۱۲۳۴۵۶۷۸۹")
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
