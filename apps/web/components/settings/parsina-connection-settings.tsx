"use client"

import { useEffect, useState } from "react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { toast } from "@workspace/ui/primitives/sonner"
import { toLatinDigits, toPersianDigits } from "@workspace/ui/lib/number"

import { api, type ParsinaConnectionOut } from "@/lib/api"

function toLatinInt(value: string): string {
  return toLatinDigits(value).replace(/[^0-9]/g, "")
}

/**
 * Mirrors the API's base-URL rule: a missing scheme means HTTP (the only
 * transport Parsina documents), everything else must be a valid http(s) URL.
 * Returns null when the value cannot be used.
 */
function normalizeBaseUrl(raw: string): string | null {
  const value = raw.trim()
  if (value === "") return ""
  if (/\s/.test(value)) return null
  const hasScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(value)
  if (/^https?:/i.test(value) && !hasScheme) return null
  const withScheme = hasScheme ? value : `http://${value}`
  let url: URL
  try {
    url = new URL(withScheme)
  } catch {
    return null
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null
  if (!url.hostname) return null
  const path = url.pathname.replace(/\/+$/, "")
  return `${url.protocol}//${url.host}${path}${url.search}`
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
          toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
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
      toast.error("شناسه سازمان باید یک عدد معتبر باشد.")
      return
    }
    if (yearRaw !== "" && (!Number.isInteger(year) || (year ?? 0) < 1)) {
      toast.error("سال مالی باید یک عدد معتبر باشد.")
      return
    }
    // Reject a malformed address here instead of saving it and later reporting
    // the misleading «Parsina unreachable» on every sync.
    const normalizedBaseUrl = normalizeBaseUrl(baseUrl)
    if (normalizedBaseUrl === null) {
      toast.error(
        "آدرس سرور پارسینا معتبر نیست؛ قالب درست: http://IP:PORT/Api/V1"
      )
      return
    }
    setBusy(true)
    try {
      const data = await api.updateParsinaConnection({
        base_url: normalizedBaseUrl,
        username: username.trim(),
        password: password === "" ? null : password,
        org_id: org,
        fiscal_year: year,
      })
      apply(data)
      toast.success("تنظیمات اتصال پارسینا ذخیره شد.")
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
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
            onChange={(e) => setBaseUrl(e.target.value)}
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
            onChange={(e) => setUsername(e.target.value)}
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
            onChange={(e) => setPassword(e.target.value)}
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
            onChange={(e) => setOrgId(toLatinInt(e.target.value))}
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
            onChange={(e) => setFiscalYear(toLatinInt(e.target.value))}
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
    </div>
  )
}
