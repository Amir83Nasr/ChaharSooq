"use client"

import { LogOut } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@workspace/ui/components/drawer"
import { useIsMobile } from "@/hooks/use-mobile"

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
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent aria-label="خروج از حساب">
          <DrawerHeader className="items-center text-center">
            <span className="mb-1 flex size-10 items-center justify-center rounded-md bg-destructive/10 text-destructive">
              <LogOut className="size-5" />
            </span>
            <DrawerTitle>خروج از حساب</DrawerTitle>
            <DrawerDescription>
              آیا مطمئن هستید که می‌خواهید از پنل مدیریت خارج شوید؟
            </DrawerDescription>
          </DrawerHeader>
          <DrawerFooter className="flex-row gap-2">
            <DrawerClose render={<Button variant="outline" className="flex-1" />}>
              انصراف
            </DrawerClose>
            <Button
              variant="destructive"
              className="flex-1"
              onClick={() => void onConfirm()}
              disabled={pending}
              autoFocus
            >
              {pending ? "در حال خروج…" : "خروج"}
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="خروج از حساب">
        <DialogHeader className="items-center text-center">
          <span className="mb-1 flex size-10 items-center justify-center rounded-md bg-destructive/10 text-destructive">
            <LogOut className="size-5" />
          </span>
          <DialogTitle>خروج از حساب</DialogTitle>
          <DialogDescription>
            آیا مطمئن هستید که می‌خواهید از پنل مدیریت خارج شوید؟
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>
            انصراف
          </DialogClose>
          <Button
            variant="destructive"
            onClick={() => void onConfirm()}
            disabled={pending}
            autoFocus
          >
            {pending ? "در حال خروج…" : "خروج"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
