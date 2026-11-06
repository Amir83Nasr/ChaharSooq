import type { ReactNode } from "react"
import { cn } from "cn"

import { Spinner } from "./spinner"

/**
 * Crossfades a button label between its idle and busy states.
 *
 * Both labels sit in the same grid cell, so the button keeps the width of the
 * longer one: the swap never changes the layout or shifts neighbouring
 * content. The inactive label is hidden from assistive technology.
 */
export function BusyLabel({
  busy,
  idle,
  busyLabel,
  spinner = false,
}: {
  busy: boolean
  idle: ReactNode
  busyLabel: ReactNode
  /** Prepend the animated spinner to the busy label. */
  spinner?: boolean
}) {
  return (
    <span className="inline-grid place-items-center">
      <span
        aria-hidden={busy || undefined}
        className={cn(
          "col-start-1 row-start-1 transition-opacity duration-200 ease-out motion-reduce:transition-none",
          busy ? "opacity-0" : "opacity-100"
        )}
      >
        {idle}
      </span>
      <span
        aria-hidden={busy ? undefined : true}
        className={cn(
          "col-start-1 row-start-1 transition-opacity duration-200 ease-out motion-reduce:transition-none",
          busy ? "opacity-100" : "opacity-0"
        )}
      >
        {spinner ? (
          <span className="inline-flex items-center gap-1">
            <Spinner active={busy} />
            {busyLabel}
          </span>
        ) : (
          busyLabel
        )}
      </span>
    </span>
  )
}
