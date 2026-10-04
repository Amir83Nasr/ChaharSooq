import { Skeleton } from "@workspace/ui/components/skeleton"

export default function DashboardLoading() {
  return (
    <div className="flex flex-1 flex-col gap-4" aria-label="در حال بارگذاری">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
