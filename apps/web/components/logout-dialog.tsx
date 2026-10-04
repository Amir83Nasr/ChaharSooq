"use client"

import { Button } from "@workspace/ui/components/button"
import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/components/responsive-dialog"

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
        <ResponsiveDialogFooter className="flex-col-reverse sm:flex-row">
          <ResponsiveDialogClose
            render={
              <Button variant="outline" className="w-full sm:w-auto" />
            }
          >
            انصراف
          </ResponsiveDialogClose>
          <Button
            variant="destructive"
            className="w-full sm:w-auto"
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
