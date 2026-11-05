import Link from "next/link"

import { Compass, LayoutDashboard, Store } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { EmptyState } from "@workspace/ui/feedback/state"

export default function NotFound() {
  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden p-6">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute top-1/2 left-1/2 size-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-muted/50 blur-3xl" />
        <div className="bg-grid-pattern absolute inset-0 opacity-60" />
      </div>

      <div className="relative w-full max-w-md">
        <EmptyState
          icon={<Compass className="size-8" />}
          title="صفحه یافت نشد"
          hint="نشانی وارد شده معتبر نیست. ممکن است صفحه جابه‌جا یا حذف شده باشد."
          action={
            <>
              <Button nativeButton={false} render={<Link href="/products" />}>
                <Store className="size-4" />
                بازگشت به محصولات
              </Button>
              <Button
                variant="outline"
                nativeButton={false}
                render={<Link href="/dashboard" />}
              >
                <LayoutDashboard className="size-4" />
                رفتن به داشبورد
              </Button>
            </>
          }
        />
      </div>
    </div>
  )
}
