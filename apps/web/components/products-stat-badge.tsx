import { PersianNumber } from "@workspace/ui/components/persian-number"

type StatColor = "emerald" | "red" | "sky" | "amber"

const STAT_STYLES: Record<StatColor, { wrap: string; dot: string }> = {
  sky: {
    wrap: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
    dot: "bg-sky-500",
  },
  red: {
    wrap: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
    dot: "bg-red-500",
  },
  emerald: {
    wrap: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    dot: "bg-emerald-500",
  },
  amber: {
    wrap: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    dot: "bg-amber-500",
  },
}

export function StatBadge({
  color,
  label,
  value,
}: {
  color: StatColor
  label: string
  value: number
}) {
  const styles = STAT_STYLES[color]
  return (
    <span
      className={
        `inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${styles.wrap}`
      }
    >
      <span aria-hidden="true" className="relative flex size-2 shrink-0">
        <span
          className={`absolute inline-flex h-full w-full animate-ping rounded-full ${styles.dot} opacity-60`}
        />
        <span className={`relative inline-flex size-2 rounded-full ${styles.dot}`} />
      </span>
      {label} <strong><PersianNumber value={value} /></strong>
    </span>
  )
}
