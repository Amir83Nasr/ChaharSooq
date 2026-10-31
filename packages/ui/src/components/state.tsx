import { AlertCircle } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

type StateProps = {
  title: string
  hint?: string
  action?: React.ReactNode
  icon?: React.ReactNode
  className?: string
}

export function EmptyState({
  title,
  hint,
  action,
  icon,
  className,
}: StateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border bg-card px-6 py-16 text-center shadow-sm ring-1 ring-foreground/5",
        className
      )}
    >
      {icon ? (
        <div className="mb-4 rounded-full bg-muted p-4 text-muted-foreground">
          {icon}
        </div>
      ) : null}
      <p className="text-lg font-semibold">{title}</p>
      {hint ? (
        <p className="mt-1 max-w-md text-sm text-muted-foreground">{hint}</p>
      ) : null}
      {action ? (
        <div className="mt-6 flex flex-wrap justify-center gap-2">{action}</div>
      ) : null}
    </div>
  )
}

export function ErrorState({
  title,
  hint,
  action,
  icon,
  className,
}: StateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border bg-card px-6 py-16 text-center shadow-sm ring-1 ring-foreground/5",
        className
      )}
    >
      <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-muted text-destructive">
        {icon ?? <AlertCircle className="size-7" />}
      </div>
      <p className="text-lg font-semibold">{title}</p>
      {hint ? (
        <p className="mt-1 max-w-md text-sm text-muted-foreground">{hint}</p>
      ) : null}
      {action ? (
        <div className="mt-6 flex flex-wrap justify-center gap-2">{action}</div>
      ) : null}
    </div>
  )
}
