import { describe, expect, it } from "vitest"

import {
  addJalaliMonths,
  buildJalaliMonth,
  compareJalaliParts,
  formatJalaliParts,
  fromJalaliParts,
  jalaliDaySpan,
  jalaliMonthLength,
  jalaliPartsToIsoDay,
  jalaliWeekdayIndex,
  toJalaliPartsUtc,
} from "./jalali"

const DAY_MS = 86_400_000

describe("Jalali conversion", () => {
  it("maps the Nowruz boundaries", () => {
    expect(jalaliPartsToIsoDay({ year: 1404, month: 1, day: 1 })).toBe(
      "2025-03-21"
    )
    expect(jalaliPartsToIsoDay({ year: 1405, month: 1, day: 1 })).toBe(
      "2026-03-21"
    )
    expect(jalaliPartsToIsoDay({ year: 1404, month: 12, day: 29 })).toBe(
      "2026-03-20"
    )
  })

  it("round-trips every day across several years", () => {
    let time = Date.UTC(2023, 0, 1)
    const end = Date.UTC(2030, 11, 31)
    while (time <= end) {
      const day = new Date(time)
      const iso = day.toISOString().slice(0, 10)
      expect(jalaliPartsToIsoDay(toJalaliPartsUtc(day))).toBe(iso)
      expect(fromJalaliParts(toJalaliPartsUtc(day)).toISOString()).toBe(
        day.toISOString()
      )
      time += DAY_MS
    }
  })

  it("counts inclusive day spans", () => {
    const nowruz = { year: 1404, month: 1, day: 1 }
    const yearEnd = { year: 1404, month: 12, day: 29 }
    expect(jalaliDaySpan(nowruz, nowruz)).toBe(1)
    expect(jalaliDaySpan(yearEnd, nowruz)).toBe(365)
    expect(jalaliDaySpan(nowruz, yearEnd)).toBe(365)
  })

  it("knows month lengths and the leap Esfand", () => {
    expect(jalaliMonthLength(1404, 1)).toBe(31)
    expect(jalaliMonthLength(1404, 7)).toBe(30)
    expect(jalaliMonthLength(1403, 12)).toBe(30)
    expect(jalaliMonthLength(1404, 12)).toBe(29)
  })
})

describe("Jalali calendar grid", () => {
  it("starts the week on Saturday", () => {
    expect(jalaliWeekdayIndex({ year: 1405, month: 1, day: 1 })).toBe(0)
    expect(jalaliWeekdayIndex({ year: 1404, month: 1, day: 1 })).toBe(6)

    const cells = buildJalaliMonth({ year: 1404, month: 1 })
    expect(cells.slice(0, 6)).toEqual([null, null, null, null, null, null])
    expect(cells[6]).toEqual({ year: 1404, month: 1, day: 1 })
    expect(cells.length % 7).toBe(0)
  })

  it("shifts months and clamps the day to the target month", () => {
    expect(addJalaliMonths({ year: 1404, month: 12, day: 30 }, 0)).toEqual({
      year: 1404,
      month: 12,
      day: 29,
    })
    expect(addJalaliMonths({ year: 1404, month: 1, day: 31 }, 1)).toEqual({
      year: 1404,
      month: 2,
      day: 31,
    })
    expect(addJalaliMonths({ year: 1404, month: 1, day: 1 }, -1)).toEqual({
      year: 1403,
      month: 12,
      day: 1,
    })
  })
})

describe("Jalali display", () => {
  it("formats with Persian digits and U+066B separators", () => {
    expect(formatJalaliParts({ year: 1404, month: 8, day: 5 })).toBe(
      "۱۴۰۴٫۰۸٫۰۵"
    )
    expect(
      compareJalaliParts(
        { year: 1404, month: 1, day: 2 },
        { year: 1404, month: 1, day: 10 }
      )
    ).toBeLessThan(0)
  })
})
