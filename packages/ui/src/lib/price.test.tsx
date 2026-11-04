import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { Price } from "../components/persian/price"
import { formatPersianNumber } from "./number"

describe("<Price />", () => {
  it("renders grouped persian digits with a single تومان label", () => {
    const html = renderToStaticMarkup(<Price value={1000000} />)
    expect(html).toContain(formatPersianNumber(1000000))
    expect(html).not.toMatch(/[0-9]/)
    // One visual glyph (aria-hidden) + one screen-reader label.
    expect(html.match(/تومان/g)?.length).toBe(2)
  })
})
