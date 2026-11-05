"use client"

import Link from "next/link"

import { AlertTriangle, Home, RefreshCw } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { ErrorState } from "@workspace/ui/feedback/state"

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden p-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
      >
        <div className="absolute top-1/2 left-1/2 size-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-muted/50 blur-3xl" />
        <div className="bg-grid-pattern absolute inset-0 opacity-60" />
      </div>

      <div className="w-full max-w-md">
        <ErrorState
          icon={<AlertTriangle className="size-8" />}
          title="خطایی رخ داد"
          hint="مشکلی در بارگذاری این صفحه پیش آمد. لطفاً دوباره تلاش کنید."
          action={
            <>
              <Button onClick={reset} className="h-11 md:h-8">
                <RefreshCw className="size-4" />
                تلاش مجدد
              </Button>
              <Button
                variant="outline"
                nativeButton={false}
                render={<Link href="/products" />}
                className="h-11 md:h-8"
              >
                <Home className="size-4" />
                بازگشت به خانه
              </Button>
            </>
          }
        />
        {error.digest ? (
          <p className="mt-4 text-center text-xs text-muted-foreground">
            کد پیگیری: {error.digest}
          </p>
        ) : null}
      </div>
    </div>
  )
}
