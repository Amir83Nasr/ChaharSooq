import type { ProductOut } from "./api"

export type StockStatus = "in" | "low" | "out"

/** Fallback until server settings load. Low means 1..threshold in stock, out means 0. */
export const DEFAULT_LOW_STOCK_THRESHOLD = 10

export const STOCK_LABELS: Record<StockStatus, string> = {
  in: "موجود",
  low: "کم",
  out: "ناموجود",
}

export function stockStatus(stock: number, threshold: number = DEFAULT_LOW_STOCK_THRESHOLD): StockStatus {
  if (stock <= 0) return "out"
  if (stock <= Math.max(threshold, 0)) return "low"
  return "in"
}

export interface InventorySummary {
  total: number
  in: number
  low: number
  out: number
  /** Sum of price * stock over items. Machine value, format with <Price/>. */
  stockValue: number
}

export function summarizeInventory(items: ProductOut[], threshold: number = DEFAULT_LOW_STOCK_THRESHOLD): InventorySummary {
  let ok = 0
  let low = 0
  let out = 0
  let stockValue = 0
  for (const item of items) {
    const status = stockStatus(item.stock, threshold)
    if (status === "in") ok += 1
    else if (status === "low") low += 1
    else out += 1
    stockValue += item.price * item.stock
  }
  return { total: items.length, in: ok, low, out, stockValue }
}
