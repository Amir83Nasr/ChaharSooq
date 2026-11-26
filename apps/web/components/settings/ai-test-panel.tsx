"use client"

import { useRef, useState } from "react"
import { FlaskConical, Square } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { Spinner } from "@workspace/ui/primitives/spinner"
import { Textarea } from "@workspace/ui/primitives/textarea"
import { toast } from "@workspace/ui/primitives/sonner"
import { formatPersianNumber } from "@workspace/ui/lib/number"

import { api, type AIStreamDone } from "@/lib/api"

const DEFAULT_PROMPT = "سلام! در یک جمله کوتاه بگو آماده‌ای."

/** Streams one prompt through the saved AI configuration. */
export function AITestPanel() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [reply, setReply] = useState("")
  const [done, setDone] = useState<AIStreamDone | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  async function runTest() {
    const text = prompt.trim()
    if (text === "" || busy) return

    const controller = new AbortController()
    controllerRef.current = controller
    setBusy(true)
    setError(null)
    setReply("")
    setDone(null)

    try {
      await api.streamAIConnection(
        text,
        {
          onDelta: (chunk) => setReply((previous) => previous + chunk),
          onDone: setDone,
        },
        controller.signal
      )
    } catch (err: unknown) {
      // A user-triggered stop is not an error; the partial reply stays.
      if (err instanceof DOMException && err.name === "AbortError") return
      const message = err instanceof Error ? err.message : "خطایی رخ داد."
      setError(message)
      toast.error(message)
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
      setBusy(false)
    }
  }

  function stopTest() {
    controllerRef.current?.abort()
  }

  const showReply = reply !== "" || done !== null || busy

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm leading-6 text-muted-foreground">
        یک درخواست واقعی با همان آدرس پایه، کلید API، شناسه مدل و دستور سیستمی
        ذخیره‌شده فرستاده می‌شود و پاسخ مدل به صورت زنده، تکه‌تکه نمایش داده
        می‌شود.
      </p>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">متن آزمایش</span>
        <Textarea
          dir="rtl"
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          aria-label="متن آزمایش هوش مصنوعی"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          onClick={runTest}
          disabled={busy || prompt.trim() === ""}
          aria-busy={busy}
          variant="outline"
          className="h-11 gap-2 sm:h-9"
        >
          {busy ? (
            <Spinner active />
          ) : (
            <FlaskConical className="size-4" aria-hidden="true" />
          )}
          <span>آزمایش اتصال</span>
        </Button>
        {busy ? (
          <Button
            type="button"
            onClick={stopTest}
            variant="ghost"
            className="h-11 gap-2 sm:h-9"
            aria-label="توقف دریافت پاسخ"
          >
            <Square className="size-3.5" aria-hidden="true" />
            توقف
          </Button>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-sm leading-6 text-destructive">
          {error}
        </p>
      ) : null}
      {showReply ? (
        <div className="rounded-2xl border bg-muted/40 p-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {done ? (
              <>
                <span dir="auto">مدل: {done.model}</span>
                <span>
                  زمان پاسخ: {formatPersianNumber(done.latency_ms)} میلی‌ثانیه
                </span>
              </>
            ) : busy ? (
              <span role="status" className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="size-1.5 animate-pulse rounded-full bg-primary"
                />
                در حال دریافت پاسخ…
              </span>
            ) : (
              <span>پاسخ ناقص</span>
            )}
          </div>
          <p dir="auto" className="mt-2 text-sm leading-7 whitespace-pre-wrap">
            {reply || (busy ? "…" : "")}
          </p>
        </div>
      ) : null}
    </div>
  )
}
