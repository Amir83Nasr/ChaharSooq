import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/components/responsive-dialog"
import { Price } from "@workspace/ui/components/price"
import { PersianDate } from "@workspace/ui/components/persian-date"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { statusVariant } from "@/components/products-stock-cell"
import { STOCK_LABELS, stockStatus, type StockStatus } from "@/lib/inventory"
import type { CategoryOut, ProductOut } from "@/lib/api"

export function CategoryDialog(props: {
  open: boolean
  categories: CategoryOut[]
  newCat: string
  catError: string | null
  catBusy: boolean
  onOpen: (v: boolean) => void
  onNewCat: (v: string) => void
  onAdd: () => void
  onRemove: (id: number) => void
  onClose: () => void
}) {
  const { open, categories, newCat, catError, catBusy, onOpen, onNewCat, onAdd, onRemove, onClose } =
    props
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpen}>
      <ResponsiveDialogContent aria-label="مدیریت دسته‌بندی‌ها">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>دسته‌بندی‌ها</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            دسته‌بندی جدید بسازید یا دسته‌بندی خالی را حذف کنید.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <div className="flex items-center gap-2">
          <Input
            value={newCat}
            onChange={(e) => onNewCat(e.target.value)}
            placeholder="نام دسته‌بندی جدید…"
            aria-label="نام دسته‌بندی جدید"
            maxLength={120}
          />
          <Button onClick={onAdd} disabled={!newCat.trim() || catBusy}>
            افزودن
          </Button>
        </div>
        {catError ? (
          <p role="alert" className="text-sm text-destructive">
            {catError}
          </p>
        ) : null}
        <ul className="flex max-h-64 min-h-0 flex-col gap-2 overflow-y-auto">
          {categories.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between gap-2 rounded-md border border-border px-2.5 py-1.5"
            >
              <span className="min-w-0 flex-1 truncate">{c.name}</span>
              <Button variant="ghost" size="sm" onClick={() => onRemove(c.id)}>
                حذف
              </Button>
            </li>
          ))}
          {categories.length === 0 ? (
            <li className="text-sm text-muted-foreground">دسته‌بندی‌ای ثبت نشده است.</li>
          ) : null}
        </ul>
        <ResponsiveDialogFooter>
          <Button variant="outline" onClick={onClose}>
            بستن
          </Button>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}

export function ProductDetailDialog(props: {
  selected: ProductOut | null
  threshold: number
  onClose: () => void
}) {
  const { selected, threshold, onClose } = props
  const status: StockStatus | null = selected ? stockStatus(selected.stock, threshold) : null
  return (
    <ResponsiveDialog open={selected !== null} onOpenChange={(open) => { if (!open) onClose() }}>
      <ResponsiveDialogContent aria-label="جزئیات کالا">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{selected?.name ?? ""}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {selected ? `کد کالا: ${selected.sku}` : ""}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {selected && status ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Badge variant={statusVariant(status)}>
                {STOCK_LABELS[status]}
                {" · "}
                <PersianNumber value={selected.stock} />
              </Badge>
              {selected.category ? (
                <Badge variant="secondary">{selected.category.name}</Badge>
              ) : null}
            </div>
            <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-md border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">موجودی</dt>
                <dd className="mt-0.5 font-semibold">
                  <PersianNumber value={selected.stock} /> عدد
                </dd>
              </div>
              <div className="rounded-md border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">قیمت</dt>
                <dd className="mt-0.5 font-semibold">
                  <Price value={selected.price} />
                </dd>
              </div>
              <div className="rounded-md border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">ارزش قلم</dt>
                <dd className="mt-0.5 font-semibold">
                  <Price value={selected.price * selected.stock} />
                </dd>
              </div>
              <div className="rounded-md border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">دسته‌بندی</dt>
                <dd className="mt-0.5 font-semibold">
                  {selected.category ? selected.category.name : "—"}
                </dd>
              </div>
              <div className="rounded-md border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">کد</dt>
                <dd className="mt-0.5 font-semibold">{selected.sku}</dd>
              </div>
              <div className="rounded-md border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">تاریخ ثبت</dt>
                <dd className="mt-0.5 font-semibold">
                  <PersianDate value={selected.created_at} />
                </dd>
              </div>
            </dl>
          </>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
