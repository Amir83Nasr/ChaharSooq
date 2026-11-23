"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, toast, type ToasterProps } from "sonner"
import {
  CircleCheckIcon,
  InfoIcon,
  TriangleAlertIcon,
  OctagonXIcon,
  Loader2Icon,
} from "lucide-react"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      dir="rtl"
      theme={theme as ToasterProps["theme"]}
      className="toaster group font-sans"
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
          // Sonner ships its own system font stack; inherit IRANYekanX instead.
          fontFamily: "inherit",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast:
            "rounded-2xl bg-popover text-popover-foreground shadow-md ring-1 ring-foreground/10",
        },
      }}
      {...props}
    />
  )
}

export { Toaster, toast }
