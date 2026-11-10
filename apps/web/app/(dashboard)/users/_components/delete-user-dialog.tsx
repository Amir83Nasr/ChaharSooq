"use client"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/primitives/responsive-dialog"

import type { UserOut } from "@/lib/api"

type DeleteUserDialogProps = {
  user: UserOut | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void | Promise<void>
  pending: boolean
  error: string | null
}

/** Delete confirmation — centered dialog on desktop, bottom sheet on mobile. */
export function DeleteUserDialog({
  user,
  onOpenChange,
  onConfirm,
  pending,
  error,
}: DeleteUserDialogProps) {
  return (
    <ResponsiveDialog open={user !== null} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent aria-label="حذف حساب کاربری">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>حذف حساب کاربری</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            حساب{" "}
            <span dir="ltr" className="font-semibold text-foreground">
              {user?.username ?? ""}
            </span>{" "}
            برای همیشه حذف می‌شود و نشست‌های فعال آن بسته می‌شوند. این کار قابل
            بازگشت نیست.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {/* No layout classes here: DrawerFooter stacks full-width on mobile,
            DialogFooter right-aligns a row on desktop. */}
        <ResponsiveDialogFooter>
          <ResponsiveDialogClose
            render={
              <Button
                variant="outline"
                disabled={pending}
                className="h-11 w-full md:h-9 md:w-auto"
              />
            }
          >
            انصراف
          </ResponsiveDialogClose>
          <Button
            variant="destructive"
            className="h-11 w-full md:h-9 md:w-auto"
            onClick={() => void onConfirm()}
            disabled={pending}
            aria-busy={pending}
            autoFocus
          >
            <BusyLabel
              busy={pending}
              idle="حذف حساب"
              busyLabel="در حال حذف…"
              spinner
            />
          </Button>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
