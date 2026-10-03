import type { ComponentProps } from "react"

import { formatPersianNumber } from "../lib/number"

type PersianNumberProps = {
  value: number | string | bigint
} & ComponentProps<"span">

export function PersianNumber({ value, ...props }: PersianNumberProps) {
  return <span {...props}>{formatPersianNumber(value)}</span>
}
