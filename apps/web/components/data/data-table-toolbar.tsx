import * as React from "react"

import { cn } from "@workspace/ui/lib/utils"
import { Input as InputPrimitive } from "@workspace/ui/primitives/input"
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
  // The flex basis is 0, so without a real min-width the row's fixed filters
  // squeeze this box down to nothing (the input then spills out of it). A
  // minimum width also makes the box take part in line breaking, so the
  // filters wrap instead of crushing the search field.
  return (
    <div className="relative min-w-44 flex-1 sm:min-w-56">
      <Search className="absolute end-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
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
    <div className={cn("rounded-2xl border bg-card p-3", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        {children}
      </div>
    </div>
  )
}
