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

const ResponsiveDialogContext =
  React.createContext<{ isMobile: boolean } | null>(null)

function useResponsiveDialogMobile() {
  const context = React.useContext(ResponsiveDialogContext)
  if (!context) {
    throw new Error(
      "ResponsiveDialog parts must be used within a ResponsiveDialog."
    )
  }
  return context.isMobile
}

type ResponsiveDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
  showSwipeHandle?: boolean
}

/** Centered dialog on desktop, bottom sheet on mobile. */
export function ResponsiveDialog({
  open,
  onOpenChange,
  children,
  showSwipeHandle = true,
}: ResponsiveDialogProps) {
  // SSR-safe default: Dialog on server/first paint, Drawer after hydration
  // on mobile — children read this from context so root and parts agree.
  const isMobile = useIsMobile()
  const value = React.useMemo(() => ({ isMobile }), [isMobile])

  if (isMobile) {
    return (
      <ResponsiveDialogContext.Provider value={value}>
        <Drawer
          open={open}
          onOpenChange={onOpenChange}
          showSwipeHandle={showSwipeHandle}
        >
          {children}
        </Drawer>
      </ResponsiveDialogContext.Provider>
    )
  }

  return (
    <ResponsiveDialogContext.Provider value={value}>
      <Dialog open={open} onOpenChange={onOpenChange}>
        {children}
      </Dialog>
    </ResponsiveDialogContext.Provider>
  )
}

type TriggerProps = {
  render: React.ReactElement
  children?: React.ReactNode
  disabled?: boolean
}

export function ResponsiveDialogTrigger(props: TriggerProps) {
  const isMobile = useResponsiveDialogMobile()

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
  const isMobile = useResponsiveDialogMobile()

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
  const isMobile = useResponsiveDialogMobile()

  if (isMobile) {
    return <DrawerHeader {...props} />
  }

  return <DialogHeader {...props} />
}

export function ResponsiveDialogTitle(
  props: React.ComponentProps<typeof DialogTitle>
) {
  const isMobile = useResponsiveDialogMobile()

  if (isMobile) {
    return <DrawerTitle {...props} />
  }

  return <DialogTitle {...props} />
}

export function ResponsiveDialogDescription(
  props: React.ComponentProps<typeof DialogDescription>
) {
  const isMobile = useResponsiveDialogMobile()

  if (isMobile) {
    return <DrawerDescription {...props} />
  }

  return <DialogDescription {...props} />
}

export function ResponsiveDialogFooter(
  props: React.ComponentProps<typeof DialogFooter>
) {
  const isMobile = useResponsiveDialogMobile()

  if (isMobile) {
    return <DrawerFooter {...props} />
  }

  return <DialogFooter {...props} />
}

export function ResponsiveDialogClose(props: TriggerProps) {
  const isMobile = useResponsiveDialogMobile()

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
