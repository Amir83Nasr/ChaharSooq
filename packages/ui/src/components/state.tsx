import { cn } from "@workspace/ui/lib/utils"

type StateProps = {
  title: string
  hint?: string
  action?: React.ReactNode
  className?: string
}

export function EmptyState({ title, hint, action, className }: StateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className
      )}
    >
      <p className="font-medium">{title}</p>
      {hint ? <p className="text-sm text-muted-foreground">{hint}</p> : null}
      {action}
    </div>
  )
}

export function ErrorState({ title, hint, action, className }: StateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-6 py-12 text-center",
        className
      )}
    >
      <p className="font-medium">{title}</p>
      {hint ? <p className="text-sm text-muted-foreground">{hint}</p> : null}
      {action}
    </div>
  )
}
