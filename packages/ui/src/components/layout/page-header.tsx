import { cn } from "@workspace/ui/lib/utils"

type PageHeaderProps = {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        // Mobile is app-like: centered title clears the floating menu button
        // on both sides; desktop keeps the start-aligned row layout.
        "flex flex-col items-center gap-4 text-center md:flex-row md:items-start md:justify-between md:text-start",
        className
      )}
    >
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle ? (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex w-full flex-wrap items-center justify-center gap-2 sm:w-auto">
          {actions}
        </div>
      ) : null}
    </div>
  )
}
