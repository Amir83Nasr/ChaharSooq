"use client"

import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/primitives/responsive-dialog"
import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { formatPersianDateTime } from "@workspace/ui/lib/date"

import type { BackupRecord } from "@/lib/api"

type BackupDeleteDialogProps = {
  backup: BackupRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void | Promise<void>
  pending: boolean
}

/** Confirmation for permanently removing one stored archive. */
export function BackupDeleteDialog({
  backup,
  open,
  onOpenChange,
  onConfirm,
  pending,
}: BackupDeleteDialogProps) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent aria-label="حذف نسخه پشتیبان">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>حذف نسخه پشتیبان</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {backup ? (
              <>
                نسخه ثبت‌شده در {formatPersianDateTime(backup.created_at)} و
                فایل آن برای همیشه حذف می‌شود.
              </>
            ) : null}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

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
          >
            <BusyLabel
              busy={pending}
              idle="حذف نسخه"
              busyLabel="در حال حذف…"
              spinner
            />
          </Button>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
