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

/** Gregorian/machne value in, Jalali parts out. No formatting here. */
export function toJalaliParts(value: Date | string | number): JalaliParts {
  const date = value instanceof Date ? value : new Date(value)
  const parts = partsFormatter.formatToParts(date)
  const get = (type: string) =>
    Number(parts.find((p) => p.type === type)?.value ?? NaN)
  return { year: get("year"), month: get("month"), day: get("day") }
}
