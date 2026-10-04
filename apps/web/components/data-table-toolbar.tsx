import * as React from "react"

import { cn } from "@workspace/ui/lib/utils"
import { Input as InputPrimitive } from "@workspace/ui/components/input"
import { Search } from "lucide-react"

type SearchInputProps = Omit<
  React.ComponentProps<typeof InputPrimitive>,
  "onChange"
> & {
  value: string
  onChange: (value: string) => void
}

export function SearchInput({
  value,
  onChange,
  placeholder = "جستجو…",
  className,
  ...props
}: SearchInputProps) {
  return (
    <div className="relative min-w-0 flex-1">
      <Search className="absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <InputPrimitive
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn("pe-10", className)}
        {...props}
      />
    </div>
  )
}

export function DataTableToolbar({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-lg border bg-card p-3", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">{children}</div>
    </div>
  )
}
