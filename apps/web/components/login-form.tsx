"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Lock, User } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { api, ApiRequestError } from "@/lib/api"

export function LoginForm() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [fieldErrors, setFieldErrors] = useState<{ username?: string; password?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const canSubmit = username.trim().length > 0 && password.length > 0 && !pending

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setFieldErrors({})
    setFormError(null)
    const next: typeof fieldErrors = {}
    if (!username.trim()) next.username = "نام کاربری را وارد کنید."
    if (!password) next.password = "گذرواژه را وارد کنید."
    if (next.username || next.password) {
      setFieldErrors(next)
      return
    }
    setPending(true)
    try {
      await api.login(username.trim(), password)
      router.push("/dashboard")
      router.refresh()
    } catch (err) {
      if (err instanceof ApiRequestError && err.code === "validation_error" && err.details) {
        const mapped: typeof fieldErrors = {}
        for (const [field, messages] of Object.entries(err.details)) {
          const key = field.split(".").pop()
          if (key === "username" || key === "password") mapped[key] = messages[0]
        }
        if (mapped.username || mapped.password) {
          setFieldErrors(mapped)
          return
        }
      }
      setFormError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSubmit} className="flex flex-col gap-6" noValidate={false}>
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-2xl font-bold">ورود به چهارسوق</h1>
          <p className="text-sm text-balance text-muted-foreground">
            برای ورود به پنل مدیریت، اطلاعات خود را وارد کنید.
          </p>
        </div>

        <div className="flex w-full flex-col gap-2">
          <label htmlFor="username" className="text-sm font-medium">
            نام کاربری
          </label>
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5">
              <User className="size-4 text-muted-foreground" />
            </div>
            <Input
              id="username"
              name="username"
              type="text"
              dir="ltr"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              aria-invalid={fieldErrors.username ? true : undefined}
              aria-describedby={fieldErrors.username ? "username-error" : undefined}
              className="h-9 bg-background pr-8 text-left"
              required
            />
          </div>
          {fieldErrors.username ? (
            <p id="username-error" role="alert" className="text-sm font-normal text-destructive">
              {fieldErrors.username}
            </p>
          ) : null}
        </div>

        <div className="flex w-full flex-col gap-2">
          <label htmlFor="password" className="text-sm font-medium">
            گذرواژه
          </label>
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5">
              <Lock className="size-4 text-muted-foreground" />
            </div>
            <Input
              id="password"
              name="password"
              type="password"
              dir="ltr"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={fieldErrors.password ? true : undefined}
              aria-describedby={fieldErrors.password ? "password-error" : undefined}
              className="h-9 bg-background pr-8"
              required
            />
          </div>
          {fieldErrors.password ? (
            <p id="password-error" role="alert" className="text-sm font-normal text-destructive">
              {fieldErrors.password}
            </p>
          ) : null}
        </div>

        {formError ? (
          <p role="alert" className="text-sm font-normal text-destructive">
            {formError}
          </p>
        ) : null}

        <div className="flex w-full flex-col gap-2">
          <Button type="submit" className="h-9 w-full md:h-9" disabled={!canSubmit}>
            {pending ? "در حال ورود…" : "ورود"}
          </Button>
        </div>
      </form>
    </div>
  )
}
