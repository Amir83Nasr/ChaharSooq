import { Badge } from "@workspace/ui/primitives/badge"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import type { StockStatus } from "@/lib/inventory"

export function statusVariant(
  status: StockStatus
): "success" | "warning" | "destructive" {
  if (status === "out") return "destructive"
  if (status === "low") return "warning"
  return "success"
}

/** Stock count cell: badge when in (green), low (amber) or out (red). */
export function StockCell({
  value,
  threshold,
}: {
  value: number
  threshold: number
}) {
  if (value <= 0) {
    return (
      <Badge variant="destructive">
        <PersianNumber value={value} />
      </Badge>
    )
  }
  if (value <= Math.max(threshold, 0)) {
    return (
      <Badge variant="warning">
        <PersianNumber value={value} />
      </Badge>
    )
  }
  return (
    <Badge variant="success">
      <PersianNumber value={value} />
    </Badge>
  )
}
