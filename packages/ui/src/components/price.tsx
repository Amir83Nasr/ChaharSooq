import type { ComponentProps } from "react"

import { cn } from "cn"

import { formatToman } from "../lib/currency"

type PriceProps = {
  value: number | bigint
} & ComponentProps<"span">

// ponytail: Toman glyph font not yet provided — .toman-glyph hook in
// globals.css takes --font-toman when it lands; upgrade path needs no
// component change. sr-only label keeps the amount accessible meanwhile.
export function Price({ value, className, ...props }: PriceProps) {
  return (
    <span className={cn(className)} {...props}>
      {formatToman(value)} <span className="toman-glyph" aria-hidden="true" />
      <span className="sr-only">تومان</span>
    </span>
  )
}
