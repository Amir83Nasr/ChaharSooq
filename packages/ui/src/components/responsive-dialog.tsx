"use client"

import * as React from "react"

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@workspace/ui/components/dialog"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@workspace/ui/components/drawer"
import { useIsMobile } from "@workspace/ui/hooks/use-mobile"

type ResponsiveDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

/** Centered dialog on desktop, bottom sheet on mobile. */
export function ResponsiveDialog({
  open,
  onOpenChange,
  children,
}: ResponsiveDialogProps) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        {children}
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {children}
    </Dialog>
  )
}

type TriggerProps = {
  render: React.ReactElement
  children?: React.ReactNode
  disabled?: boolean
}

export function ResponsiveDialogTrigger(props: TriggerProps) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <DrawerTrigger render={props.render} disabled={props.disabled}>
        {props.children}
      </DrawerTrigger>
    )
  }

  return (
    <DialogTrigger render={props.render} disabled={props.disabled}>
      {props.children}
    </DialogTrigger>
  )
}

type ContentProps = {
  className?: string
  children: React.ReactNode
  showCloseButton?: boolean
  "aria-label"?: string
}

export function ResponsiveDialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: ContentProps) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <DrawerContent className={className} {...props}>
        {children}
      </DrawerContent>
    )
  }

  return (
    <DialogContent
      className={className}
      showCloseButton={showCloseButton}
      {...props}
    >
      {children}
    </DialogContent>
  )
}

export function ResponsiveDialogHeader(
  props: React.ComponentProps<typeof DialogHeader>
) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return <DrawerHeader {...props} />
  }

  return <DialogHeader {...props} />
}

export function ResponsiveDialogTitle(
  props: React.ComponentProps<typeof DialogTitle>
) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return <DrawerTitle {...props} />
  }

  return <DialogTitle {...props} />
}

export function ResponsiveDialogDescription(
  props: React.ComponentProps<typeof DialogDescription>
) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return <DrawerDescription {...props} />
  }

  return <DialogDescription {...props} />
}

export function ResponsiveDialogFooter(
  props: React.ComponentProps<typeof DialogFooter>
) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return <DrawerFooter {...props} />
  }

  return <DialogFooter {...props} />
}

export function ResponsiveDialogClose(props: TriggerProps) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <DrawerClose render={props.render} disabled={props.disabled}>
        {props.children}
      </DrawerClose>
    )
  }

  return (
    <DialogClose render={props.render} disabled={props.disabled}>
      {props.children}
    </DialogClose>
  )
}
