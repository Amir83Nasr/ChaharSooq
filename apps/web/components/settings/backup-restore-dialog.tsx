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
import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { toPersianDigits } from "@workspace/ui/lib/number"

import type { BackupRecord } from "@/lib/api"

type BackupRestoreDialogProps = {
  backup: BackupRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void | Promise<void>
  pending: boolean
  error: string | null
}

/** Final confirmation before replacing shop data from one stored archive. */
export function BackupRestoreDialog({
  backup,
  open,
  onOpenChange,
  onConfirm,
  pending,
  error,
}: BackupRestoreDialogProps) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent aria-label="بازیابی از پشتیبان">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>بازیابی از پشتیبان</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {backup ? (
              <>
                داده‌های فروشگاه با نسخه ثبت‌شده در{" "}
                {formatPersianDateTime(backup.created_at)} جایگزین می‌شود.
              </>
            ) : null}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {toPersianDigits(error)}
          </p>
        ) : null}

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
              idle="بازیابی نسخه"
              busyLabel="در حال بازیابی…"
              spinner
            />
          </Button>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
