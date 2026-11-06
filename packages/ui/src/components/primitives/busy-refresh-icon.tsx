import { RefreshCw } from "lucide-react"
import { cn } from "cn"

import { Spinner } from "./spinner"

/**
 * Refresh glyph that crossfades into a spinner while busy.
 *
 * Toggling `animate-spin` on a mounted icon makes it snap back to 0deg when
 * the run ends, which reads as a jump. Here the spinner stays mounted (paused
 * while idle) and only opacity animates, so both state changes stay smooth.
 */
export function BusyRefreshIcon({
  busy,
  className,
}: {
  busy: boolean
  className?: string
}) {
  return (
    <span
      data-icon="inline-start"
      aria-hidden="true"
      className={cn("relative inline-flex size-4 shrink-0", className)}
    >
      <RefreshCw
        className={cn(
          "absolute inset-0 size-4 transition-opacity duration-200 ease-out motion-reduce:transition-none",
          busy ? "opacity-0" : "opacity-100"
        )}
      />
      <Spinner active={busy} className="absolute inset-0" />
    </span>
  )
}
