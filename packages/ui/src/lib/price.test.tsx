import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { Price } from "../components/persian/price"
import { TomanGlyph } from "../components/persian/toman-glyph"
import { formatPersianNumber } from "./number"

describe("<Price />", () => {
  it("renders grouped persian digits with a single تومان label", () => {
    const html = renderToStaticMarkup(<Price value={1000000} />)
    expect(html).toContain(formatPersianNumber(1000000))
    expect(html).not.toMatch(/[0-9]/)
    // One visual glyph (aria-hidden) + one plain screen-reader label.
    expect(html.match(/تومان/g)?.length).toBe(2)
    expect(html).toContain('class="toman-glyph"')
    expect(html).toContain("تومانءء")
    expect(html).toContain('<span class="sr-only">تومان</span>')
  })
})

describe("<TomanGlyph />", () => {
  it("renders the visible Toman word through the shared glyph hook", () => {
    const html = renderToStaticMarkup(<TomanGlyph className="text-xs" />)
    expect(html).toContain('class="toman-glyph text-xs"')
    expect(html).toContain('aria-hidden="true"')
    expect(html.match(/تومانءء/g)?.length).toBe(1)
    expect(html).not.toContain("sr-only")
  })
})
