import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"
import { Button } from "@workspace/ui/components/button"
import { PersianNumber } from "@workspace/ui/components/persian-number"

function Pagination({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      role="navigation"
      aria-label="صفحه‌بندی"
      data-slot="pagination"
      className={cn("mx-auto flex w-full justify-center", className)}
      {...props}
    />
  )
}

function PaginationContent({
  className,
  ...props
}: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="pagination-content"
      className={cn("flex items-center gap-1", className)}
      {...props}
    />
  )
}

function PaginationItem({ ...props }: React.ComponentProps<"li">) {
  return <li data-slot="pagination-item" {...props} />
}

function PaginationPrevious({
  className,
  children = "قبلی",
  ...props
}: React.ComponentProps<typeof Button>) {
  return (
    <Button
      variant="ghost"
      data-slot="pagination-previous"
      className={cn(className)}
      {...props}
    >
      <ChevronRight />
      <span>{children}</span>
    </Button>
  )
}

function PaginationNext({
  className,
  children = "بعدی",
  ...props
}: React.ComponentProps<typeof Button>) {
  return (
    <Button
      variant="ghost"
      data-slot="pagination-next"
      className={cn(className)}
      {...props}
    >
      <span>{children}</span>
      <ChevronLeft />
    </Button>
  )
}

function TablePagination({
  page,
  totalPages,
  onPageChange,
  children,
}: {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  children?: React.ReactNode
}) {
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between px-4 py-3">
      <p className="text-sm text-muted-foreground">
        صفحه <PersianNumber value={page} /> از{" "}
        <PersianNumber value={totalPages} />
      </p>
      <div className="flex items-center gap-2">
        <Pagination className="mx-0 w-auto">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                aria-label="صفحه قبلی"
                disabled={page <= 1}
                onClick={() => onPageChange(page - 1)}
              />
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                aria-label="صفحه بعدی"
                disabled={page >= totalPages}
                onClick={() => onPageChange(page + 1)}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
        {children}
      </div>
    </div>
  )
}

export {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
  TablePagination,
}
