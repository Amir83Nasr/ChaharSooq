import type { ProductTableColumn } from "./api-types"

export interface ProductTableColumnMeta {
  id: ProductTableColumn
  /** Header / settings label. */
  label: string
  /** Short explanation shown in the settings card. */
  hint: string
  /** Width for the fixed table layout. */
  widthClass: string
  /** Same width in pixels, for the table's minimum width. */
  minWidthPx: number
  center?: boolean
}

// Canonical order — the table renders in this order and the settings card
// offers the same sequence. Keep in sync with backend PRODUCT_TABLE_COLUMNS.
export const PRODUCT_TABLE_COLUMNS: readonly ProductTableColumnMeta[] = [
  {
    id: "row",
    label: "ردیف",
    hint: "شماره ترتیب کالا در جدول",
    widthClass: "w-12",
    minWidthPx: 48,
    center: true,
  },
  {
    id: "name",
    label: "نام",
    hint: "نام کامل کالا",
    widthClass: "w-56",
    minWidthPx: 224,
  },
  {
    id: "sku",
    label: "کد",
    hint: "کد یکتای کالا در حسابداری",
    widthClass: "w-32",
    minWidthPx: 128,
    center: true,
  },
  {
    id: "category",
    label: "دسته‌بندی",
    hint: "دسته اصلی: فرش، مبلمان یا لوازم خانگی",
    widthClass: "w-24",
    minWidthPx: 96,
    center: true,
  },
  {
    id: "brand",
    label: "برند",
    hint: "برند و زیرگروه کالا",
    widthClass: "w-40",
    minWidthPx: 160,
  },
  {
    id: "unit",
    label: "واحد",
    hint: "واحد فروش کالا",
    widthClass: "w-20",
    minWidthPx: 80,
    center: true,
  },
  {
    id: "price",
    label: "قیمت",
    hint: "قیمت پایه کالا در حسابداری",
    widthClass: "w-28",
    minWidthPx: 112,
    center: true,
  },
  {
    id: "competitor_price",
    label: "قیمت رقبا",
    hint: "قیمت رقیب در بازار انتخاب‌شده",
    widthClass: "w-36",
    minWidthPx: 144,
    center: true,
  },
  {
    id: "price_diff",
    label: "اختلاف درصد",
    hint: "درصد اختلاف قیمت ما با رقیب",
    widthClass: "w-28",
    minWidthPx: 112,
    center: true,
  },
  {
    id: "suggested_price",
    label: "قیمت پیشنهادی",
    hint: "ترکیب قیمت پایه و قیمت رقیب",
    widthClass: "w-32",
    minWidthPx: 128,
    center: true,
  },
  {
    id: "stock",
    label: "موجودی",
    hint: "موجودی انبار و وضعیت کمبود",
    widthClass: "w-24",
    minWidthPx: 96,
    center: true,
  },
]

export const DEFAULT_PRODUCT_TABLE_COLUMNS: readonly ProductTableColumn[] =
  PRODUCT_TABLE_COLUMNS.map((column) => column.id)

const KNOWN_COLUMNS = new Set<string>(DEFAULT_PRODUCT_TABLE_COLUMNS)

export function isProductTableColumn(
  value: string
): value is ProductTableColumn {
  return KNOWN_COLUMNS.has(value)
}

/** Orders a stored selection canonically and drops unknown / empty values. */
export function normalizeProductTableColumns(
  value: readonly string[] | null | undefined
): ProductTableColumn[] {
  if (!value || value.length === 0) return [...DEFAULT_PRODUCT_TABLE_COLUMNS]
  const selected = new Set(value.filter(isProductTableColumn))
  const ordered = PRODUCT_TABLE_COLUMNS.filter((column) =>
    selected.has(column.id)
  ).map((column) => column.id)
  return ordered.length > 0 ? ordered : [...DEFAULT_PRODUCT_TABLE_COLUMNS]
}

/** Minimum table width for the visible columns, so hidden columns free space. */
export function productTableMinWidth(
  columns: readonly ProductTableColumn[]
): number {
  const shown = new Set(columns)
  return PRODUCT_TABLE_COLUMNS.filter((column) => shown.has(column.id)).reduce(
    (total, column) => total + column.minWidthPx,
    0
  )
}
