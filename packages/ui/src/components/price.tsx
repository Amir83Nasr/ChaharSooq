import type { ComponentProps } from "react"

import { cn } from "cn"

import { formatToman } from "../lib/currency"

type PriceProps = {
  value: number | bigint
} & ComponentProps<"span">

// ponytail: Toman glyph "تومانءءء" uses fallback font until --font-toman
// lands; no API change.
export function Price({ value, className, ...props }: PriceProps) {
  return (
    <span className={cn(className)} {...props}>
      {formatToman(value)}{" "}
      <span className="toman-glyph" aria-hidden="true">
        تومانءء
      </span>
      <span className="sr-only">تومان</span>
    </span>
  )
}
