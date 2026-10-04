import Link from "next/link"

import { Button } from "@workspace/ui/components/button"
import { EmptyState } from "@workspace/ui/components/state"

export default function NotFound() {
  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <EmptyState
        title="صفحه یافت نشد"
        hint="نشانی وارد شده معتبر نیست."
        action={
          <Button render={<Link href="/products" />}>بازگشت به محصولات</Button>
        }
      />
    </div>
  )
}
