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
      <ResponsiveDialogContent aria-label="جزئیات کالا">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{selected?.name ?? ""}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {selected ? `کد کالا: ${selected.sku}` : ""}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {selected ? (
          <>
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
            <section className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-6 text-center">
              <h3 className="text-sm font-semibold">تنظیمات اتصال</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                این بخش در حال توسعه است و تنظیمات اتصال در فاز بعدی به آن اضافه
                می‌شود.
              </p>
            </section>
          </>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
