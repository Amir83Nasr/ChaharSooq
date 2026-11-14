"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { toLatinDigits, toPersianDigits } from "@workspace/ui/lib/number"

import { api, type ParsinaConnectionOut } from "@/lib/api"

function toLatinInt(value: string): string {
  return toLatinDigits(value).replace(/[^0-9]/g, "")
}

export function ParsinaConnectionSettings() {
  const [baseUrl, setBaseUrl] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [orgId, setOrgId] = useState("")
  const [fiscalYear, setFiscalYear] = useState("")
  const [passwordSet, setPasswordSet] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  function apply(data: ParsinaConnectionOut) {
    setBaseUrl(data.base_url ?? "")
    setUsername(data.username ?? "")
    setOrgId(data.org_id != null ? String(data.org_id) : "")
    setFiscalYear(data.fiscal_year != null ? String(data.fiscal_year) : "")
    setPasswordSet(data.password_set)
    setPassword("")
  }

  useEffect(() => {
    let cancelled = false
    api
      .parsinaConnection()
      .then((data) => {
        if (!cancelled) {
          apply(data)
          setLoaded(true)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "خطایی رخ داد.")
          setLoaded(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function save() {
    const orgRaw = orgId.trim()
    const yearRaw = fiscalYear.trim()
    const org = orgRaw === "" ? null : Number(orgRaw)
    const year = yearRaw === "" ? null : Number(yearRaw)
    if (orgRaw !== "" && (!Number.isInteger(org) || (org ?? 0) < 1)) {
      setError("شناسه سازمان باید یک عدد معتبر باشد.")
      setSaved(false)
      return
    }
    if (yearRaw !== "" && (!Number.isInteger(year) || (year ?? 0) < 1)) {
      setError("سال مالی باید یک عدد معتبر باشد.")
      setSaved(false)
      return
    }
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateParsinaConnection({
        base_url: baseUrl.trim(),
        username: username.trim(),
        password: password === "" ? null : password,
        org_id: org,
        fiscal_year: year,
      })
      apply(data)
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-40 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        اطلاعات اتصال به وب‌سرویس پارسینا طبق مستندات: آدرس سرور، نام کاربری،
        رمز عبور، شناسه سازمان و سال مالی.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 sm:col-span-2">
          <span className="text-sm font-medium">آدرس سرور (Base URL)</span>
          <Input
            dir="ltr"
            value={baseUrl}
            onChange={(e) => {
              setBaseUrl(e.target.value)
              setSaved(false)
            }}
            placeholder="http://IP:PORT/Api/V1"
            aria-label="آدرس سرور پارسینا"
            className="h-11 sm:h-9"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">نام کاربری</span>
          <Input
            dir="ltr"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value)
              setSaved(false)
            }}
            autoComplete="off"
            aria-label="نام کاربری پارسینا"
            className="h-11 sm:h-9"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">رمز عبور</span>
          <Input
            dir="ltr"
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              setSaved(false)
            }}
            autoComplete="new-password"
            placeholder={
              passwordSet ? "ذخیره شده است (برای تغییر وارد کنید)" : "رمز عبور"
            }
            aria-label="رمز عبور پارسینا"
            className="h-11 sm:h-9"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">شناسه سازمان (org)</span>
          <Input
            dir="ltr"
            inputMode="numeric"
            value={orgId ? toPersianDigits(orgId) : ""}
            onChange={(e) => {
              setOrgId(toLatinInt(e.target.value))
              setSaved(false)
            }}
            placeholder="مثلاً ۱"
            aria-label="شناسه سازمان پارسینا"
            className="h-11 sm:h-9"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">سال مالی (year)</span>
          <Input
            dir="ltr"
            inputMode="numeric"
            value={fiscalYear ? toPersianDigits(fiscalYear) : ""}
            onChange={(e) => {
              setFiscalYear(toLatinInt(e.target.value))
              setSaved(false)
            }}
            placeholder="مثلاً ۱۴۰۳"
            aria-label="سال مالی پارسینا"
            className="h-11 sm:h-9"
          />
        </label>
      </div>
      <div className="flex items-center gap-3">
        <Button
          onClick={save}
          disabled={busy}
          aria-busy={busy}
          className="h-11 shrink-0 sm:h-9"
        >
          <BusyLabel
            busy={busy}
            idle="ذخیره اتصال"
            busyLabel={<span className="sr-only">در حال ذخیره…</span>}
            spinner
          />
        </Button>
        {passwordSet ? (
          <span className="text-xs text-muted-foreground">
            رمز عبور تنظیم شده است.
          </span>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {toPersianDigits(error)}
        </p>
      ) : null}
      {saved ? (
        <p role="status" className="text-sm text-success">
          تنظیمات اتصال پارسینا ذخیره شد.
        </p>
      ) : null}
    </div>
  )
}
