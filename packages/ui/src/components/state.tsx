import { cn } from "@workspace/ui/lib/utils"

type StateProps = {
  title: string
  hint?: string
  action?: React.ReactNode
  icon?: React.ReactNode
  className?: string
}

export function EmptyState({ title, hint, action, icon, className }: StateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border bg-card px-6 py-16 text-center ring-1 ring-foreground/10",
        className
      )}
    >
      {icon ? (
        <div className="mb-4 rounded-full bg-muted p-4">{icon}</div>
      ) : null}
      <p className="text-lg font-semibold">{title}</p>
      {hint ? (
        <p className="mt-1 text-sm text-muted-foreground">{hint}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export function ErrorState({ title, hint, action, icon, className }: StateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-destructive/40 bg-destructive/5 px-6 py-16 text-center ring-1 ring-destructive/10",
        className
      )}
    >
      {icon ? (
        <div className="mb-4 rounded-full bg-destructive/10 p-4">{icon}</div>
      ) : null}
      <p className="text-lg font-semibold">{title}</p>
      {hint ? (
        <p className="mt-1 text-sm text-muted-foreground">{hint}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
