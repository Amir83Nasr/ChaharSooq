"use client"

import { useCallback, useEffect, useState } from "react"
import { Plus, Trash2, UserRound } from "lucide-react"

import { Badge } from "@workspace/ui/primitives/badge"
import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"
import { Input } from "@workspace/ui/primitives/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/primitives/select"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { PersianDateTime } from "@workspace/ui/persian/persian-date"

import {
  api,
  ApiRequestError,
  type AssignableRole,
  type UserOut,
  type UserRole,
} from "@/lib/api"

const ROLE_LABELS: Record<UserRole, string> = {
  owner: "مالک",
  admin: "مدیر",
  viewer: "کاربر",
}

type FieldErrors = {
  username?: string
  password?: string
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "خطایی رخ داد. لطفاً دوباره تلاش کنید."
}

export function UsersView({
  currentUsername,
  isOwner,
}: {
  currentUsername: string
  isOwner: boolean
}) {
  const [users, setUsers] = useState<UserOut[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState<AssignableRole>("viewer")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setUsers(await api.users())
      setLoadError(null)
    } catch (error) {
      setLoadError(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function createUser(event: React.FormEvent) {
    event.preventDefault()
    setFieldErrors({})
    setFormError(null)
    setCreated(null)

    const next: FieldErrors = {}
    const trimmed = username.trim()
    if (trimmed.length < 3)
      next.username = "نام کاربری باید حداقل ۳ نویسه باشد."
    if (password.length < 8) next.password = "گذرواژه باید حداقل ۸ نویسه باشد."
    if (next.username || next.password) {
      setFieldErrors(next)
      return
    }

    setCreating(true)
    try {
      const user = await api.createUser({
        username: trimmed,
        password,
        role,
      })
      setUsers((current) => [...(current ?? []), user])
      setCreated(user.username)
      setUsername("")
      setPassword("")
      setRole("viewer")
    } catch (error) {
      if (
        error instanceof ApiRequestError &&
        error.code === "validation_error" &&
        error.details
      ) {
        const mapped: FieldErrors = {}
        for (const [field, messages] of Object.entries(error.details)) {
          const key = field.split(".").pop()
          if (key === "username" || key === "password")
            mapped[key] = messages[0]
        }
        if (mapped.username || mapped.password) {
          setFieldErrors(mapped)
          return
        }
      }
      setFormError(errorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  async function deleteUser(user: UserOut) {
    if (
      !window.confirm(
        `حساب «${user.username}» حذف شود؟ این کار قابل بازگشت نیست.`
      )
    )
      return
    setDeletingId(user.id)
    setFormError(null)
    try {
      await api.deleteUser(user.id)
      setUsers((current) =>
        (current ?? []).filter((item) => item.id !== user.id)
      )
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setDeletingId(null)
    }
  }

  const canSubmit =
    username.trim().length >= 3 && password.length >= 8 && !creating

  return (
    <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserRound className="size-4" aria-hidden="true" />
            افزودن کاربر
          </CardTitle>
          <CardDescription>
            «کاربر» فقط می‌تواند اطلاعات و مشخصات را ببیند؛ «مدیر» همه بخش‌ها را
            مدیریت می‌کند.
            {isOwner
              ? " به‌عنوان مالک می‌توانید مدیر هم بسازید."
              : " ساخت مدیر فقط توسط مالک انجام می‌شود."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={createUser}
            className="flex flex-col gap-4"
            noValidate
          >
            <div className="flex flex-col gap-2">
              <label htmlFor="new-username" className="text-sm font-medium">
                نام کاربری
              </label>
              <Input
                id="new-username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                dir="ltr"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                aria-invalid={fieldErrors.username ? true : undefined}
                aria-describedby={
                  fieldErrors.username ? "new-username-error" : undefined
                }
                className="h-10 bg-background text-left"
                required
              />
              {fieldErrors.username ? (
                <p
                  id="new-username-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {fieldErrors.username}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="new-password" className="text-sm font-medium">
                گذرواژه
              </label>
              <Input
                id="new-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                dir="ltr"
                autoComplete="new-password"
                aria-invalid={fieldErrors.password ? true : undefined}
                aria-describedby={
                  fieldErrors.password ? "new-password-error" : undefined
                }
                className="h-10 bg-background text-left"
                required
              />
              {fieldErrors.password ? (
                <p
                  id="new-password-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {fieldErrors.password}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium">سطح دسترسی</span>
              {isOwner ? (
                <Select
                  value={role}
                  onValueChange={(value) => setRole(value as AssignableRole)}
                >
                  <SelectTrigger
                    className="h-10 w-full"
                    aria-label="سطح دسترسی"
                  >
                    <SelectValue>
                      {(value: string | null) =>
                        value
                          ? (ROLE_LABELS[value as UserRole] ?? "کاربر")
                          : "کاربر"
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent align="start">
                    <SelectItem value="viewer">کاربر — فقط مشاهده</SelectItem>
                    <SelectItem value="admin">مدیر — دسترسی کامل</SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                  کاربر — فقط مشاهده
                </p>
              )}
            </div>

            {formError ? (
              <p role="alert" className="text-sm text-destructive">
                {formError}
              </p>
            ) : null}
            {created ? (
              <p role="status" className="text-sm text-success">
                حساب «{created}» ساخته شد.
              </p>
            ) : null}

            <Button
              type="submit"
              disabled={!canSubmit}
              aria-busy={creating}
              className="h-11 w-full md:h-9"
            >
              <BusyLabel
                busy={creating}
                idle={
                  <span className="inline-flex items-center gap-1">
                    <Plus className="size-4" aria-hidden="true" />
                    افزودن کاربر
                  </span>
                }
                busyLabel="در حال ساخت…"
                spinner
              />
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>حساب‌های کاربری</CardTitle>
          <CardDescription>
            هر حساب با نام کاربری و گذرواژه خودش وارد می‌شود.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2" aria-label="در حال بارگذاری کاربران">
              {Array.from({ length: 3 }, (_, index) => (
                <Skeleton key={index} className="h-14 w-full rounded-2xl" />
              ))}
            </div>
          ) : loadError ? (
            <div className="flex flex-col items-start gap-3">
              <p role="alert" className="text-sm text-destructive">
                {loadError}
              </p>
              <Button variant="outline" onClick={() => void load()}>
                تلاش مجدد
              </Button>
            </div>
          ) : users && users.length > 0 ? (
            <ul className="divide-y divide-border">
              {users.map((user) => {
                const isSelf = user.username === currentUsername
                return (
                  <li
                    key={user.id}
                    className="flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-bold">
                        {user.username.slice(0, 1)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium" dir="ltr">
                          {user.username}
                          {isSelf ? (
                            <span className="ms-2 text-xs font-normal text-muted-foreground">
                              (شما)
                            </span>
                          ) : null}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          ساخته‌شده در{" "}
                          <PersianDateTime value={user.created_at} />
                        </p>
                      </div>
                    </div>
                    <Badge
                      variant={user.role === "viewer" ? "secondary" : "default"}
                    >
                      {ROLE_LABELS[user.role]}
                    </Badge>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={
                        isSelf || user.role === "owner" || deletingId !== null
                      }
                      aria-busy={deletingId === user.id}
                      onClick={() => void deleteUser(user)}
                      className="h-9 gap-1.5"
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      حذف
                    </Button>
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              هنوز کاربری ساخته نشده است.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
