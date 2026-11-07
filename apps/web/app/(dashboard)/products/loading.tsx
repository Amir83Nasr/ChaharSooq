import { Skeleton } from "@workspace/ui/primitives/skeleton"

/* Route-level fallback (shown while the products segment streams in). It is a
   lightweight shape-only skeleton — importing the real table module here would
   pull the whole client table into the transition payload. */
export default function ProductsLoading() {
  return (
    <div
      className="flex flex-1 flex-col gap-4"
      aria-label="در حال بارگذاری محصولات"
    >
      <div className="flex flex-col items-center gap-3 md:flex-row md:items-start md:justify-between">
        <div className="flex flex-col items-center gap-2 md:items-start">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-44" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-36" />
          <Skeleton className="h-9 w-36" />
        </div>
      </div>

      <Skeleton className="h-11 w-full md:h-9" />

      <div className="space-y-2.5 md:hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-40 w-full rounded-2xl" />
        ))}
      </div>

      <div className="hidden overflow-hidden rounded-2xl border md:block">
        <Skeleton className="h-11 w-full rounded-none" />
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="border-t px-4 py-3">
            <Skeleton className="h-5 w-full" />
          </div>
        ))}
      </div>
    </div>
  )
}
