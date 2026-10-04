"use client"

import { Button } from "@workspace/ui/components/button"
import { ErrorState } from "@workspace/ui/components/state"

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <ErrorState
        title="خطایی رخ داد"
        hint={error.message}
        action={<Button onClick={reset}>تلاش مجدد</Button>}
      />
    </div>
  )
}
