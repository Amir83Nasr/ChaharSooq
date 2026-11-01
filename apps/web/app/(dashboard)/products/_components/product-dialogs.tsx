import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/components/responsive-dialog"
import { Price } from "@workspace/ui/components/price"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import type { ProductOut } from "@/lib/api"
import { ProductCompetitorPrices } from "./product-competitor-prices"

export function ProductDetailDialog(props: {
  selected: ProductOut | null
  onClose: () => void
}) {
  const { selected, onClose } = props
  return (
    <ResponsiveDialog
      open={selected !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <ResponsiveDialogContent
        aria-label="جزئیات کالا"
        className="max-h-[90dvh] max-w-3xl overflow-y-auto"
      >
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{selected?.name ?? ""}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {selected ? `کد کالا: ${selected.sku}` : ""}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {selected ? (
          <div className="min-h-0 space-y-4 overflow-y-auto">
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
            </dl>
            {!selected.main_group_name?.startsWith("فرش") &&
            !selected.main_group_name?.startsWith("مبلمان") ? (
              <ProductCompetitorPrices productId={selected.id} />
            ) : null}
          </div>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
