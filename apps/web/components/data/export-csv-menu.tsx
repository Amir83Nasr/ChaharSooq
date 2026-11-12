"use client"

import { useState } from "react"
import { Download } from "lucide-react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/primitives/dropdown-menu"
import { Spinner } from "@workspace/ui/primitives/spinner"

import { ApiRequestError } from "@/lib/api"
import { downloadFile } from "@/lib/download"

export interface ExportCsvOption {
  label: string
  description?: string
  /** Built lazily so the current filters are read at click time. */
  buildUrl: () => string
}

/**
 * "خروجی گرفتن از اطلاعات" menu shared by the products page and the store pages.
 *
 * One download at a time: the trigger stays busy until the file starts, and
 * API errors (401 excepted) are shown inline instead of in a toast.
 */
export function ExportCsvMenu({
  options,
  onUnauthorized,
  label = "خروجی گرفتن از اطلاعات",
  compact = false,
}: {
  options: ExportCsvOption[]
  onUnauthorized: () => void
  label?: string
  /** Icon-only trigger for tight rows (mobile search bar). */
  compact?: boolean
}) {
  const [busyLabel, setBusyLabel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const busy = busyLabel !== null

  async function run(option: ExportCsvOption) {
    setBusyLabel(option.label)
    setError(null)
    try {
      await downloadFile(option.buildUrl(), "charsooq-export.csv", {
        onUnauthorized,
      })
    } catch (err: unknown) {
      // 401 already navigated away; any other failure stays on this page.
      if (err instanceof ApiRequestError && err.status === 401) return
      setError(
        err instanceof ApiRequestError
          ? err.message
          : "دانلود خروجی ناموفق بود. دوباره تلاش کنید."
      )
    } finally {
      setBusyLabel(null)
    }
  }

  return (
    <div
      className={
        compact
          ? "relative shrink-0"
          : "relative flex flex-col items-stretch gap-1"
      }
    >
      <DropdownMenu>
        {compact ? (
          <DropdownMenuTrigger
            render={
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={label}
                disabled={busy}
                className="size-11 shrink-0 rounded-2xl"
              />
            }
          >
            {busy ? (
              <Spinner active />
            ) : (
              <Download className="size-5" aria-hidden="true" />
            )}
          </DropdownMenuTrigger>
        ) : (
          <DropdownMenuTrigger
            render={<Button type="button" variant="outline" disabled={busy} />}
          >
            <Download className="size-4" aria-hidden="true" />
            <BusyLabel
              busy={busy}
              idle={label}
              busyLabel={busyLabel ?? label}
              spinner
            />
          </DropdownMenuTrigger>
        )}
        <DropdownMenuContent align="end" className="w-64">
          {/* Base UI GroupLabel must live inside a Group. */}
          <DropdownMenuGroup>
            <DropdownMenuLabel>دریافت فایل CSV</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {options.map((option) => (
              <DropdownMenuItem
                key={option.label}
                disabled={busy}
                onClick={() => void run(option)}
              >
                <div className="flex min-w-0 flex-col gap-0.5 text-start">
                  <span>{option.label}</span>
                  {option.description ? (
                    <span className="text-xs text-muted-foreground">
                      {option.description}
                    </span>
                  ) : null}
                </div>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {error ? (
        <p
          role="alert"
          className={
            compact
              ? "absolute end-0 top-full z-20 mt-1 w-52 rounded-xl border bg-popover px-2 py-1.5 text-xs text-destructive shadow-sm"
              : "max-w-64 text-xs text-destructive"
          }
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}
