"use client"

import * as React from "react"

// Estimated row height (px) used before a row is measured. Real heights are
// observed per row (see below); the estimate only sizes the initial spacers.
const EST_ROW_HEIGHT = 52
// Rows rendered above/below the viewport so fast scrolling never flashes gaps.
const OVERSCAN_ROWS = 8
// First paint (and SSR) renders this many rows deterministically.
const INITIAL_ROWS = 40

export type RowWindow = {
  start: number
  end: number
  topPad: number
  bottomPad: number
}

/** Deterministic first-paint window (also used for SSR). */
export function initialRowWindow(count: number): RowWindow {
  const end = Math.min(count, INITIAL_ROWS)
  return { start: 0, end, topPad: 0, bottomPad: (count - end) * EST_ROW_HEIGHT }
}

/**
 * Windowed rendering for long tables ("show all" renders the whole catalog).
 * Only the viewport slice + overscan stays mounted, so a sidebar toggle or a
 * theme flip reflows dozens of rows instead of thousands.
 *
 * Rows keep variable heights: each rendered row is measured with a shared
 * ResizeObserver (keyed by item id, so widths changing mid-animation just
 * refresh the cache) and spacers fill the rest. No new dependency.
 *
 * The scroll container is the dashboard scroll div
 * (`[data-slot="dashboard-scroll"]` in the dashboard layout); the table
 * itself only scrolls horizontally.
 */
export function useWindowedRows(
  count: number,
  keyAt: (index: number) => string | number
): {
  bodyRef: React.RefObject<HTMLTableSectionElement | null>
  observeRow: (index: number) => (el: HTMLTableRowElement | null) => void
  win: RowWindow
} {
  const bodyRef = React.useRef<HTMLTableSectionElement | null>(null)
  const rowEls = React.useRef(new Map<number, HTMLTableRowElement>())
  const heights = React.useRef(new Map<string | number, number>())
  const roRef = React.useRef<ResizeObserver | null>(null)
  const rafRef = React.useRef(0)
  const keyAtRef = React.useRef(keyAt)
  keyAtRef.current = keyAt
  const countRef = React.useRef(count)
  countRef.current = count

  const [win, setWin] = React.useState<RowWindow>(() => initialRowWindow(count))

  const recompute = React.useCallback(() => {
    rafRef.current = 0
    const body = bodyRef.current
    const container = body?.closest(
      '[data-slot="dashboard-scroll"]'
    ) as HTMLElement | null
    // No scroll container (or SSR): render everything.
    if (!body || !container) {
      setWin((w) =>
        w.start === 0 &&
        w.end === countRef.current &&
        w.topPad === 0 &&
        w.bottomPad === 0
          ? w
          : { start: 0, end: countRef.current, topPad: 0, bottomPad: 0 }
      )
      return
    }
    const count = countRef.current
    const bodyRect = body.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    const relTop = container.scrollTop + (bodyRect.top - containerRect.top)
    const viewTop = Math.max(0, relTop - OVERSCAN_ROWS * EST_ROW_HEIGHT)
    const viewBottom =
      relTop + containerRect.height + OVERSCAN_ROWS * EST_ROW_HEIGHT

    let acc = 0
    let start = 0
    let end = count
    let topPad = 0
    for (let i = 0; i < count; i++) {
      const h = heightAtRefValue(i)
      if (acc + h <= viewTop) {
        acc += h
        start = i + 1
        topPad = acc
      } else if (acc < viewBottom) {
        acc += h
        end = i + 1
      } else {
        break
      }
    }
    let bottomPad = 0
    for (let i = end; i < count; i++) bottomPad += heightAtRefValue(i)

    setWin((w) =>
      w.start === start &&
      w.end === end &&
      Math.abs(w.topPad - topPad) < 1 &&
      Math.abs(w.bottomPad - bottomPad) < 1
        ? w
        : { start, end, topPad, bottomPad }
    )

    function heightAtRefValue(index: number): number {
      return heights.current.get(keyAtRef.current(index)) ?? EST_ROW_HEIGHT
    }
  }, [])

  const schedule = React.useCallback(() => {
    if (rafRef.current) return
    rafRef.current = requestAnimationFrame(() => recompute())
  }, [recompute])

  // Mount: observe rows + container, listen to scroll, sync with restored scroll.
  React.useEffect(() => {
    const body = bodyRef.current
    const container = body?.closest(
      '[data-slot="dashboard-scroll"]'
    ) as HTMLElement | null
    if (!body || !container) return

    const ro = new ResizeObserver((entries) => {
      let changed = false
      for (const entry of entries) {
        if (entry.target === container) {
          changed = true
          continue
        }
        const index = Number((entry.target as HTMLElement).dataset.vi)
        if (!Number.isInteger(index)) continue
        const h = entry.contentRect.height
        const prev = heights.current.get(keyAtRef.current(index))
        if (h > 0 && (prev === undefined || Math.abs(prev - h) > 0.5)) {
          heights.current.set(keyAtRef.current(index), h)
          changed = true
        }
      }
      if (changed) schedule()
    })
    roRef.current = ro
    rowEls.current.forEach((el) => ro.observe(el))
    ro.observe(container)

    const onScroll = () => schedule()
    container.addEventListener("scroll", onScroll, { passive: true })
    // Catches restored scroll positions (back/forward navigation).
    schedule()
    return () => {
      container.removeEventListener("scroll", onScroll)
      ro.disconnect()
      roRef.current = null
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = 0
    }
  }, [schedule])

  // Row count changes (new fetch/filter): recompute the window.
  React.useEffect(() => {
    schedule()
  }, [count, schedule])

  // Stable per-index callbacks: a fresh closure every render would make
  // React detach/reattach every row ref on each scroll render.
  const cbCache = React.useRef(
    new Map<number, (el: HTMLTableRowElement | null) => void>()
  )
  const observeRow = React.useCallback((index: number) => {
    let cb = cbCache.current.get(index)
    if (!cb) {
      cb = (el: HTMLTableRowElement | null) => {
        const prev = rowEls.current.get(index)
        if (prev && prev !== el) {
          roRef.current?.unobserve(prev)
          rowEls.current.delete(index)
        }
        if (el) {
          el.dataset.vi = String(index)
          rowEls.current.set(index, el)
          roRef.current?.observe(el)
        }
      }
      cbCache.current.set(index, cb)
    }
    return cb
  }, [])

  // Drop element refs that no longer exist (unmounted rows).
  React.useEffect(() => {
    rowEls.current.forEach((el, index) => {
      if (!el.isConnected) {
        roRef.current?.unobserve(el)
        rowEls.current.delete(index)
      }
    })
  })

  return { bodyRef, observeRow, win }
}
