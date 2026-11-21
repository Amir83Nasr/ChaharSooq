import type { ComponentProps } from "react"

import { cn } from "cn"

type TomanGlyphProps = Omit<ComponentProps<"span">, "children">

// The trailing hamzas trigger IRANYekanX's required ligature (tomaan.001).
export function TomanGlyph({ className, ...props }: TomanGlyphProps) {
  return (
    <span
      className={cn("toman-glyph", className)}
      aria-hidden="true"
      {...props}
    >
      تومانءء
    </span>
  )
}
