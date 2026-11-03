import Link from "next/link"

import { Button } from "@workspace/ui/primitives/button"
import { EmptyState } from "@workspace/ui/feedback/state"

export default function NotFound() {
  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <EmptyState
        title="صفحه یافت نشد"
        hint="نشانی وارد شده معتبر نیست."
        action={
          <Button nativeButton={false} render={<Link href="/products" />}>
            بازگشت به محصولات
          </Button>
        }
      />
    </div>
  )
}
