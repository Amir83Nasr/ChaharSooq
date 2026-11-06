"use client"

import { useEffect, useState } from "react"
import { Eye, EyeOff, RotateCcw, Save } from "lucide-react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { cn } from "@workspace/ui/lib/utils"

import { api, type ProductTableColumn } from "@/lib/api"
import {
  DEFAULT_PRODUCT_TABLE_COLUMNS,
  PRODUCT_TABLE_COLUMNS,
  normalizeProductTableColumns,
} from "@/lib/product-table-columns"

function sameColumns(
  a: readonly ProductTableColumn[],
  b: readonly ProductTableColumn[]
): boolean {
  return (
    a.length === b.length && a.every((column, index) => column === b[index])
  )
}

export function TableColumnsSettings() {
  const [value, setValue] = useState<ProductTableColumn[]>([])
  const [baseline, setBaseline] = useState<ProductTableColumn[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .settings()
      .then((data) => {
        if (cancelled) return
        const columns = normalizeProductTableColumns(data.product_table_columns)
        setValue(columns)
        setBaseline(columns)
        setLoaded(true)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // Keep the card usable with the defaults if the settings call fails;
        // the error stays visible and the next save retries the write.
        const fallback = [...DEFAULT_PRODUCT_TABLE_COLUMNS]
        setValue(fallback)
        setBaseline(fallback)
        setError(err instanceof Error ? err.message : "خطایی رخ داد.")
        setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const dirty = !sameColumns(value, baseline)
  const visible = new Set(value)

  function toggle(column: ProductTableColumn) {
    if (busy) return
    setSaved(false)
    setError(null)
    setValue((current) => {
      if (current.includes(column)) {
        // Keep at least one column so the table never renders empty.
        if (current.length === 1) return current
        return current.filter((item) => item !== column)
      }
      const selected = new Set([...current, column])
      return PRODUCT_TABLE_COLUMNS.filter((item) => selected.has(item.id)).map(
        (item) => item.id
      )
    })
  }

  async function persist(next: ProductTableColumn[]) {
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const data = await api.updateSettings({ product_table_columns: next })
      const columns = normalizeProductTableColumns(data.product_table_columns)
      setValue(columns)
      setBaseline(columns)
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
        className="h-24 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-muted-foreground">
          <PersianNumber value={value.length} /> از{" "}
          <PersianNumber value={PRODUCT_TABLE_COLUMNS.length} /> ستون نمایش داده
          می‌شود.
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={busy || sameColumns(value, DEFAULT_PRODUCT_TABLE_COLUMNS)}
          onClick={() => persist([...DEFAULT_PRODUCT_TABLE_COLUMNS])}
        >
          <RotateCcw aria-hidden="true" />
          بازگردانی همه ستون‌ها
        </Button>
      </div>

      <div
        className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3"
        role="group"
        aria-label="ستون‌های جدول محصولات"
      >
        {PRODUCT_TABLE_COLUMNS.map((column) => {
          const active = visible.has(column.id)
          const lastVisible = active && value.length === 1
          return (
            <Button
              key={column.id}
              type="button"
              variant={active ? "default" : "outline"}
              aria-pressed={active}
              aria-disabled={lastVisible || undefined}
              disabled={busy || lastVisible}
              title={
                lastVisible ? "حداقل یک ستون باید نمایش داده شود." : column.hint
              }
              onClick={() => toggle(column.id)}
              className={cn(
                "h-11 justify-between gap-2 px-3 md:h-9",
                !active && "text-muted-foreground"
              )}
            >
              <span className="flex min-w-0 items-center gap-2">
                {active ? (
                  <Eye className="size-4 shrink-0" aria-hidden="true" />
                ) : (
                  <EyeOff className="size-4 shrink-0" aria-hidden="true" />
                )}
                <span className="truncate">{column.label}</span>
              </span>
              <span
                className={cn(
                  "text-[11px] font-normal",
                  active
                    ? "text-primary-foreground/80"
                    : "text-muted-foreground"
                )}
              >
                {active ? "نمایش" : "پنهان"}
              </span>
            </Button>
          )
        })}
      </div>

      <div className="flex flex-col gap-3 border-t border-border/70 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-h-5 text-xs" role="status">
          {error ? (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          ) : saved ? (
            <p className="text-success">ستون‌های جدول ذخیره شد.</p>
          ) : dirty ? (
            <p className="text-amber-700 dark:text-amber-300">
              تغییرات ذخیره نشده است.
            </p>
          ) : (
            <p className="text-muted-foreground">
              این تنظیم برای همه دستگاه‌ها اعمال می‌شود.
            </p>
          )}
        </div>
        <Button
          type="button"
          onClick={() => persist(value)}
          disabled={busy || !dirty}
          className="h-11 w-full sm:w-auto"
        >
          <BusyLabel
            busy={busy}
            idle={
              <span className="inline-flex items-center gap-1">
                <Save aria-hidden="true" />
                ذخیره ستون‌ها
              </span>
            }
            busyLabel="در حال ذخیره…"
            spinner
          />
        </Button>
      </div>
    </div>
  )
}
