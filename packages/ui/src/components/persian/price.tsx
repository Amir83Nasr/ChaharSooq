import type { ComponentProps } from "react"

import { cn } from "cn"

import { formatToman } from "../../lib/currency"
import { TomanGlyph } from "./toman-glyph"

type PriceProps = {
  value: number | bigint
} & ComponentProps<"span">

export function Price({ value, className, ...props }: PriceProps) {
  return (
    <span className={cn(className)} {...props}>
      {formatToman(value)} <TomanGlyph />
      <span className="sr-only">تومان</span>
    </span>
  )
}
