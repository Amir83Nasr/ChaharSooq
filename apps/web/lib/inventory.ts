export type StockStatus = "in" | "low" | "out"

/** Fallback until server settings load. Low means 1..threshold in stock, out means 0. */
export const DEFAULT_LOW_STOCK_THRESHOLD = 5

export const STOCK_LABELS: Record<StockStatus, string> = {
  in: "موجود",
  low: "موجودی کم",
  out: "ناموجود",
}

export function stockStatus(
  stock: number,
  threshold: number = DEFAULT_LOW_STOCK_THRESHOLD
): StockStatus {
  if (stock <= 0) return "out"
  if (stock <= Math.max(threshold, 0)) return "low"
  return "in"
}
