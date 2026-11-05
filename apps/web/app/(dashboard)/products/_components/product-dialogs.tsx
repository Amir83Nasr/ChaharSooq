import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/primitives/responsive-dialog"
import { Price } from "@workspace/ui/persian/price"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import type { ProductOut } from "@/lib/api"
import { ProductCompetitorPrices } from "./product-competitor-prices"

export function ProductDetailDialog(props: {
  selected: ProductOut | null
  onClose: () => void
  onCompetitorChanged?: () => void
}) {
  const { selected, onClose, onCompetitorChanged } = props
  return (
    <ResponsiveDialog
      open={selected !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <ResponsiveDialogContent
        aria-label="جزئیات کالا"
        className="no-scrollbar max-h-[90dvh] overflow-y-auto rounded-t-2xl pb-[calc(1rem+env(safe-area-inset-bottom))] sm:max-w-5xl sm:rounded-2xl sm:pb-6"
      >
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{selected?.name ?? ""}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {selected ? `کد کالا: ${selected.sku}` : ""}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {selected ? (
          <div className="no-scrollbar min-h-0 space-y-4 overflow-y-auto">
            <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-2xl border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">موجودی</dt>
                <dd className="mt-0.5 font-semibold">
                  <PersianNumber value={selected.stock} /> عدد
                </dd>
              </div>
              <div className="rounded-2xl border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">قیمت</dt>
                <dd className="mt-0.5 font-semibold">
                  <Price value={selected.price} />
                </dd>
              </div>
            </dl>
            {!selected.main_group_name?.startsWith("فرش") &&
            !selected.main_group_name?.startsWith("مبلمان") ? (
              <ProductCompetitorPrices
                productId={selected.id}
                onChanged={onCompetitorChanged}
              />
            ) : (
              <section className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-center">
                <p className="text-sm font-medium">
                  مقایسهٔ قیمت برای این دسته‌بندی هنوز در دست پیاده‌سازی است.
                </p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  در فاز فعلی فقط کالاهای لوازم خانگی قیمت فروشگاه‌های دیگر را
                  دارند.
                </p>
              </section>
            )}
          </div>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
