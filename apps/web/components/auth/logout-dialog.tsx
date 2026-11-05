"use client"

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

type LogoutDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void | Promise<void>
  pending: boolean
}

/** Logout confirmation — centered dialog on desktop, bottom sheet on mobile. */
export function LogoutDialog({
  open,
  onOpenChange,
  onConfirm,
  pending,
}: LogoutDialogProps) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent aria-label="خروج از حساب">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>خروج از حساب کاربری</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            آیا مطمئن هستید که می‌خواهید از حساب خود خارج شوید؟ برای ورود مجدد
            باید دوباره وارد شوید.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {/* No layout classes here: DrawerFooter stacks full-width on mobile,
            DialogFooter right-aligns a row on desktop. `sm:` overrides would
            leak desktop layout into the mobile drawer (640–768px). */}
        <ResponsiveDialogFooter>
          <ResponsiveDialogClose
            render={
              <Button
                variant="outline"
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
            autoFocus
          >
            {pending ? "در حال خروج…" : "خروج از حساب"}
          </Button>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
