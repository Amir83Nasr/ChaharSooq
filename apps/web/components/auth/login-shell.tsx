import Image from "next/image"

import { LoginForm } from "@/components/auth/login-form"
import { ThemeToggle } from "@/components/layout/theme-toggle"

export function LoginShell() {
  return (
    <div className="bg-grid-pattern grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden rounded-3xl bg-muted lg:m-4 lg:block">
        <Image
          src="/images/login.jpg"
          alt="تحویل سفارش با موتور و نقشه"
          fill
          sizes="(min-width: 1024px) 50vw, 100vw"
          priority
          draggable={false}
          className="object-cover select-none"
        />
      </div>
      <div className="relative flex flex-col items-center justify-center p-6 md:p-10">
        <div className="inset-e-4 md:inset-e-6 absolute top-4 md:top-6">
          <ThemeToggle />
        </div>
        <div className="flex w-full max-w-xs flex-col justify-center">
          <LoginForm />
        </div>
      </div>
    </div>
  )
}
