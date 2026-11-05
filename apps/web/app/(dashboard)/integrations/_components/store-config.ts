import type { TopGroup } from "@/lib/api"

export type StoreKey = "sofa" | "digifresh" | "digikala" | "technolife"

export type AutoStoreKey = "digikala" | "technolife"

export interface StoreConfig {
  key: StoreKey
  name: string
  topGroup: TopGroup
  description: string
  /** Automatic price check is available (JSON-LD/API extractor exists). */
  auto: boolean
}

export const STORES: Record<StoreKey, StoreConfig> = {
  sofa: {
    key: "sofa",
    name: "سوفا",
    topGroup: "مبلمان",
    description: "قیمت محصولات مبلمان در سوفا با قیمت فروشگاه مقایسه می‌شود.",
    auto: false,
  },
  digifresh: {
    key: "digifresh",
    name: "دیجی‌فرش",
    topGroup: "فرش",
    description: "قیمت محصولات فرش در دیجی‌فرش با قیمت فروشگاه مقایسه می‌شود.",
    auto: false,
  },
  digikala: {
    key: "digikala",
    name: "دیجی‌کالا",
    topGroup: "لوازم خانگی",
    description: "قیمت لوازم خانگی در دیجی‌کالا با قیمت فروشگاه مقایسه می‌شود.",
    auto: true,
  },
  technolife: {
    key: "technolife",
    name: "تکنولایف",
    topGroup: "لوازم خانگی",
    description: "قیمت لوازم خانگی در تکنولایف با قیمت فروشگاه مقایسه می‌شود.",
    auto: true,
  },
}

export function isStoreKey(value: string): value is StoreKey {
  return (
    value === "sofa" ||
    value === "digifresh" ||
    value === "digikala" ||
    value === "technolife"
  )
}

export function isAutoStoreKey(key: StoreKey): key is AutoStoreKey {
  return STORES[key].auto
}
