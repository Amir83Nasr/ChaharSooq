"use client"

import { useEffect, useRef, useState } from "react"
import { Copy, RefreshCw, Sparkles, Square, Trash2 } from "lucide-react"

import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { formatPersianNumber } from "@workspace/ui/lib/number"
import { Button } from "@workspace/ui/primitives/button"
import { Spinner } from "@workspace/ui/primitives/spinner"
import { toast } from "@workspace/ui/primitives/sonner"

import {
  ApiRequestError,
  api,
  type AIStreamDone,
  type ProductAnalysisReport,
} from "@/lib/api"

const GENERATE_ERROR = "تهیه گزارش تحلیلی انجام نشد. دوباره تلاش کنید."
const DELETE_ERROR = "حذف گزارش انجام نشد. دوباره تلاش کنید."

type Phase = "idle" | "reading" | "writing"

/**
 * Owner-only AI report for one product. The backend assembles the context and
 * saves the last complete report; this component only names the product id,
 * renders the streamed text, and can load or delete the saved report.
 */
export function ProductAIAnalysis({
  productId,
  productName,
}: {
  productId: number
  productName: string
}) {
  const [report, setReport] = useState("")
  const [done, setDone] = useState<AIStreamDone | null>(null)
  const [saved, setSaved] = useState<ProductAnalysisReport | null>(null)
  const [loadingSaved, setLoadingSaved] = useState(true)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>("idle")
  const controllerRef = useRef<AbortController | null>(null)
  const busy = phase !== "idle"

  // The tab is keyed by product, so this runs once per dialog/product.
  useEffect(() => {
    let cancelled = false
    api
      .productAnalysisReport(productId)
      .then((data) => {
        if (cancelled) return
        setSaved(data)
        setReport(data.content)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // No saved report is the normal first-use state; other read failures
        // must not block the generate action.
        if (err instanceof ApiRequestError && err.status === 404) return
      })
      .finally(() => {
        if (!cancelled) setLoadingSaved(false)
      })
    return () => {
      cancelled = true
    }
  }, [productId])

  async function start() {
    if (busy || loadingSaved) return
    const controller = new AbortController()
    controllerRef.current = controller
    setPhase("reading")
    setError(null)
    setReport("")
    setDone(null)
    setSaved(null)
    setConfirmDelete(false)

    try {
      await api.streamProductAnalysis(
        productId,
        {
          onDelta: (chunk) => {
            setPhase("writing")
            setReport((previous) => previous + chunk)
          },
          onDone: setDone,
        },
        controller.signal
      )
    } catch (err) {
      // A user-triggered stop is not an error; the partial report stays.
      if (err instanceof DOMException && err.name === "AbortError") return
      setError(err instanceof Error ? err.message : GENERATE_ERROR)
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
      setPhase("idle")
    }
  }

  function stop() {
    controllerRef.current?.abort()
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(report)
      toast.success("گزارش کپی شد.")
    } catch {
      toast.error("کپی گزارش انجام نشد.")
    }
  }

  async function remove() {
    if (busy) return
    try {
      await api.deleteProductAnalysisReport(productId)
      setReport("")
      setDone(null)
      setSaved(null)
      setError(null)
      setConfirmDelete(false)
      toast.success("گزارش حذف شد.")
    } catch (err) {
      // A report that never reached the database is only in local state.
      if (err instanceof ApiRequestError && err.status === 404) {
        setReport("")
        setDone(null)
        setSaved(null)
        setError(null)
        setConfirmDelete(false)
        toast.success("گزارش حذف شد.")
        return
      }
      toast.error(err instanceof Error ? err.message : DELETE_ERROR)
    }
  }

  if (loadingSaved) {
    return (
      <div
        className="space-y-2 rounded-2xl border border-border/70 bg-muted/20 p-4"
        aria-label="در حال بارگذاری گزارش ذخیره‌شده"
      >
        <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
        <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
      </div>
    )
  }

  const started = report !== "" || busy || done !== null || error !== null

  return (
    <div className="flex flex-col gap-3">
      {!started ? (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-border/70 bg-muted/30 p-4">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles className="size-4" aria-hidden="true" />
          </span>
          <div className="space-y-1">
            <p className="text-sm font-medium">گزارش تحلیلی {productName}</p>
            <p className="text-xs leading-6 text-muted-foreground">
              فروش ۳۰ روز، موجودی، قیمت رقبا و پیشنهاد خرید را از دادهٔ همین
              لحظه بررسی می‌کند. گزارش پس از پایان ذخیره می‌شود و با باز کردن
              دوبارهٔ کالا باقی می‌ماند.
            </p>
          </div>
          <Button
            type="button"
            onClick={() => void start()}
            className="h-10 gap-2"
          >
            <Sparkles className="size-4" aria-hidden="true" />
            تهیه گزارش تحلیلی
          </Button>
        </div>
      ) : null}

      {started ? (
        <div className="rounded-2xl border border-border/70 bg-background/60">
          <div className="flex flex-wrap items-center gap-2 border-b border-border/70 px-3 py-2">
            <span className="flex items-center gap-1.5 text-xs font-medium">
              <Sparkles className="size-3.5 text-primary" aria-hidden="true" />
              تحلیل هوش مصنوعی
            </span>
            {busy ? (
              <span
                role="status"
                className="flex items-center gap-1.5 text-xs text-muted-foreground"
              >
                <Spinner active />
                {phase === "reading"
                  ? "در حال تحلیل داده…"
                  : "در حال نوشتن گزارش…"}
              </span>
            ) : saved ? (
              <span className="text-xs text-muted-foreground">
                ذخیره‌شده {formatPersianDateTime(saved.generated_at)} ·{" "}
                {saved.model_id}
              </span>
            ) : done ? (
              <span className="text-xs text-muted-foreground">
                {done.model} · {formatPersianNumber(done.latency_ms)} میلی‌ثانیه
              </span>
            ) : null}
            <span className="ms-auto flex items-center gap-1">
              {busy ? (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={stop}
                  className="h-8 gap-1.5 text-xs"
                  aria-label="توقف تولید گزارش"
                >
                  <Square className="size-3" aria-hidden="true" />
                  توقف
                </Button>
              ) : (
                <>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => void start()}
                    className="h-8 gap-1.5 text-xs"
                  >
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    تولید مجدد
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => void copy()}
                    disabled={report === ""}
                    className="h-8 gap-1.5 text-xs"
                  >
                    <Copy className="size-3.5" aria-hidden="true" />
                    کپی
                  </Button>
                </>
              )}
            </span>
          </div>

          <div className="px-3 py-3">
            {error ? (
              <div className="space-y-2">
                <p role="alert" className="text-xs leading-6 text-destructive">
                  {error}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void start()}
                  className="h-8 text-xs"
                >
                  تلاش دوباره
                </Button>
              </div>
            ) : null}

            {report !== "" ? (
              <div
                dir="rtl"
                className="text-[13px] leading-7 whitespace-pre-wrap"
              >
                {report}
                {busy ? (
                  <span
                    aria-hidden="true"
                    className="ms-0.5 inline-block h-4 w-1 animate-pulse bg-primary align-middle"
                  />
                ) : null}
              </div>
            ) : busy ? (
              <div className="space-y-2" aria-hidden="true">
                <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
                <div className="h-3 w-full animate-pulse rounded bg-muted" />
                <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
              </div>
            ) : null}

            {!busy && report !== "" ? (
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/70 pt-2">
                <p className="text-[11px] leading-5 text-muted-foreground">
                  این گزارش بر پایهٔ دادهٔ همین لحظه است و جای تصمیم نهایی مدیر
                  را نمی‌گیرد.
                </p>
                {saved !== null || done !== null ? (
                  confirmDelete ? (
                    <span className="flex items-center gap-1">
                      <Button
                        type="button"
                        variant="destructive"
                        onClick={() => void remove()}
                        className="h-8 text-xs"
                      >
                        حذف قطعی
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => setConfirmDelete(false)}
                        className="h-8 text-xs"
                      >
                        انصراف
                      </Button>
                    </span>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setConfirmDelete(true)}
                      className="h-8 gap-1.5 text-xs text-destructive hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                      حذف گزارش
                    </Button>
                  )
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
