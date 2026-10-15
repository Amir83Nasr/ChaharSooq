import { Badge } from "@workspace/ui/components/badge"
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
import type { ProductOut } from "@/lib/api"

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
