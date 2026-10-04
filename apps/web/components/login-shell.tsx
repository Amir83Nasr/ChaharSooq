"use client"

import { Image as ImageIcon } from "lucide-react"

import { LoginForm } from "@/components/login-form"
import { ThemeToggle } from "@/components/theme-toggle"

export function LoginShell() {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden rounded-3xl bg-muted lg:m-4 lg:block">
        <div className="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground">
          <ImageIcon className="size-12" aria-hidden="true" />
          <p className="text-sm">تصویر صفحه ورود</p>
        </div>
      </div>
      <div className="relative flex flex-col items-center justify-center p-6 md:p-10">
        <div className="absolute top-4 inset-e-4 md:top-6 md:inset-e-6">
          <ThemeToggle />
        </div>
        <div className="flex w-full max-w-xs flex-col justify-center">
          <LoginForm />
        </div>
      </div>
    </div>
  )
}
