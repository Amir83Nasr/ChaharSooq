import type { ComponentProps } from "react"

import { formatPersianDate, formatPersianDateTime } from "../lib/date"

type PersianDateProps = {
  value: Date | string | number
} & ComponentProps<"span">

export function PersianDate({ value, ...props }: PersianDateProps) {
  return <span {...props}>{formatPersianDate(value)}</span>
}

export function PersianDateTime({ value, ...props }: PersianDateProps) {
  return <span {...props}>{formatPersianDateTime(value)}</span>
}
