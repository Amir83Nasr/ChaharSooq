import type { ProductOut } from "./api"

export type StockStatus = "good" | "low" | "out"

/** Matches mock: low means 1..5 in stock, out means 0. */
export const LOW_STOCK_THRESHOLD = 5

export const STOCK_LABELS: Record<StockStatus, string> = {
  good: "مناسب",
  low: "کم",
  out: "ناموجود",
}

export function stockStatus(stock: number): StockStatus {
  if (stock <= 0) return "out"
  if (stock <= LOW_STOCK_THRESHOLD) return "low"
  return "good"
}

export interface InventorySummary {
  total: number
  good: number
  low: number
  out: number
  /** Sum of price * stock over items. Machine value, format with <Price/>. */
  stockValue: number
}

export function summarizeInventory(items: ProductOut[]): InventorySummary {
  let good = 0
  let low = 0
  let out = 0
  let stockValue = 0
  for (const item of items) {
    const status = stockStatus(item.stock)
    if (status === "good") good += 1
    else if (status === "low") low += 1
    else out += 1
    stockValue += item.price * item.stock
  }
  return { total: items.length, good, low, out, stockValue }
}
