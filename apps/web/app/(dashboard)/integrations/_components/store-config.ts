import type { TopGroup } from "@/lib/api"

export type StoreKey =
  "sofa" | "digifresh" | "digikala" | "technolife" | "torob"

export type AutoStoreKey = "digikala" | "technolife" | "torob"

export interface StoreConfig {
  key: StoreKey
  name: string
  /** Catalog sections this store is compared against. */
  topGroups: TopGroup[]
  description: string
  /** Automatic price check is available (JSON-LD/API extractor exists). */
  auto: boolean
}

export const STORES: Record<StoreKey, StoreConfig> = {
  sofa: {
    key: "sofa",
    name: "سوفا",
    topGroups: ["مبلمان"],
    description:
      "لینک محصولات مبلمان در سوفا ثبت می‌شود و تغییر روزانه قیمت مبنای پیشنهاد است.",
    auto: false,
  },
  digifresh: {
    key: "digifresh",
    name: "دیجی‌فرش",
    topGroups: ["فرش"],
    description:
      "لینک محصولات فرش در دیجی‌فرش ثبت می‌شود و تغییر روزانه قیمت مبنای پیشنهاد است.",
    auto: false,
  },
  digikala: {
    key: "digikala",
    name: "دیجی‌کالا",
    topGroups: ["لوازم خانگی", "کالای دیجیتال"],
    description:
      "قیمت لوازم خانگی و کالای دیجیتال در دیجی‌کالا با قیمت فروشگاه مقایسه می‌شود.",
    auto: true,
  },
  technolife: {
    key: "technolife",
    name: "تکنولایف",
    topGroups: ["لوازم خانگی", "کالای دیجیتال"],
    description:
      "قیمت لوازم خانگی و کالای دیجیتال در تکنولایف با قیمت فروشگاه مقایسه می‌شود.",
    auto: true,
  },
  torob: {
    key: "torob",
    name: "ترب",
    topGroups: ["لوازم خانگی", "کالای دیجیتال", "مبلمان", "فرش"],
    description:
      "قیمت تمام دستهبندیها در ترب (بازارگاه) با قیمت فروشگاه مقایسه میشود؛ فقط لینک صفحات محصول /p/ پشتیبانی میشود.",
    auto: true,
  },
}

export function isStoreKey(value: string): value is StoreKey {
  return (
    value === "sofa" ||
    value === "digifresh" ||
    value === "digikala" ||
    value === "technolife" ||
    value === "torob"
  )
}

export function isAutoStoreKey(key: StoreKey): key is AutoStoreKey {
  return STORES[key].auto
}
