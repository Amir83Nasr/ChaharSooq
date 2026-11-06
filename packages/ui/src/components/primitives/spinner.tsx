import { LoaderCircle } from "lucide-react"
import { cn } from "cn"

/**
 * Spinner that fades in and out instead of mounting/unmounting.
 *
 * `animate-spin` stays on the glyph and is only paused while inactive, so the
 * rotation never restarts from 0deg and busy → idle → busy never snaps.
 */
export function Spinner({
  active,
  className,
}: {
  active: boolean
  className?: string
}) {
  return (
    <LoaderCircle
      aria-hidden="true"
      className={cn(
        "size-4 shrink-0 animate-spin transition-opacity duration-200 ease-out motion-reduce:animate-none motion-reduce:transition-none",
        active ? "opacity-100" : "opacity-0",
        className
      )}
      style={{ animationPlayState: active ? "running" : "paused" }}
    />
  )
}
