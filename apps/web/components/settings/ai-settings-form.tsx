"use client"

import { useEffect, useState } from "react"
import { FlaskConical } from "lucide-react"

import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { Spinner } from "@workspace/ui/primitives/spinner"
import { Textarea } from "@workspace/ui/primitives/textarea"
import { toast } from "@workspace/ui/primitives/sonner"

import { api, type AISettings } from "@/lib/api"

const TEST_PROMPT = "سلام! در یک جمله کوتاه بگو آماده‌ای."

/** AI connection and shared system-prompt editor for management accounts. */
export function AISettingsForm() {
  const [baseUrl, setBaseUrl] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [modelId, setModelId] = useState("")
  const [systemPrompt, setSystemPrompt] = useState("")
  const [apiKeySet, setApiKeySet] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState(false)

  function apply(data: AISettings) {
    setBaseUrl(data.base_url ?? "")
    setModelId(data.model_id ?? "")
    setSystemPrompt(data.system_prompt ?? "")
    setApiKeySet(data.api_key_set)
    setApiKey("")
  }

  useEffect(() => {
    let cancelled = false
    api
      .aiSettings()
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
    setBusy(true)
    try {
      const data = await api.updateAISettings({
        base_url: baseUrl.trim(),
        api_key: apiKey === "" ? null : apiKey,
        model_id: modelId.trim(),
        system_prompt: systemPrompt,
      })
      apply(data)
      toast.success("تنظیمات هوش مصنوعی ذخیره شد.")
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "خطایی رخ داد.")
    } finally {
      setBusy(false)
    }
  }

  async function testConnection() {
    if (testing) return
    setTesting(true)
    try {
      await api.testAIConnection(TEST_PROMPT)
      toast.success("اتصال هوش مصنوعی درست کار می‌کند.")
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : "آزمایش اتصال انجام نشد."
      )
    } finally {
      setTesting(false)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-48 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm leading-6 text-muted-foreground">
        آدرس پایه باید به یک سرویس سازگار با OpenAI اشاره کند و مسیر تکمیل گفتگو
        به{" "}
        <span dir="ltr" className="font-mono text-xs">
          POST /chat/completions
        </span>{" "}
        اضافه می‌شود.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 sm:col-span-2">
          <span className="text-sm font-medium">آدرس پایه (Base URL)</span>
          <Input
            dir="ltr"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.gapgpt.ir/v1"
            aria-label="آدرس پایه هوش مصنوعی"
            className="h-11 sm:h-9"
          />
          <span className="text-xs text-muted-foreground">
            خالی گذاشتن این فیلد، مقدار پیش‌فرض را برمی‌گرداند.
          </span>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">شناسه مدل (Model ID)</span>
          <Input
            dir="ltr"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            placeholder="gapgpt-deepseek-v4.1-flash"
            aria-label="شناسه مدل هوش مصنوعی"
            className="h-11 sm:h-9"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">کلید API</span>
          <Input
            dir="ltr"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="new-password"
            placeholder={
              apiKeySet ? "ذخیره شده است (برای تغییر وارد کنید)" : "sk-..."
            }
            aria-label="کلید API هوش مصنوعی"
            className="h-11 sm:h-9"
          />
        </label>
        <label className="flex flex-col gap-1.5 sm:col-span-2">
          <span className="text-sm font-medium">
            دستور سیستمی (System Prompt)
          </span>
          <Textarea
            dir="rtl"
            rows={5}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="مثلاً: تو دستیار فروشگاه چهارسوق هستی و فقط فارسی پاسخ می‌دهی."
            aria-label="دستور سیستمی هوش مصنوعی"
            className="min-h-28"
          />
          <span className="text-xs text-muted-foreground">
            خالی گذاشتن آن، دستور سیستمی را پاک می‌کند.
          </span>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={save}
          disabled={busy || testing}
          aria-busy={busy}
          className="h-11 shrink-0 sm:h-9"
        >
          <BusyLabel
            busy={busy}
            idle="ذخیره تنظیمات"
            busyLabel={<span className="sr-only">در حال ذخیره…</span>}
            spinner
          />
        </Button>
        <Button
          type="button"
          onClick={testConnection}
          disabled={busy || testing}
          aria-busy={testing}
          variant="outline"
          className="h-11 shrink-0 gap-2 sm:h-9"
        >
          {testing ? (
            <Spinner active />
          ) : (
            <FlaskConical className="size-4" aria-hidden="true" />
          )}
          <span>آزمایش اتصال</span>
        </Button>
      </div>
    </div>
  )
}
