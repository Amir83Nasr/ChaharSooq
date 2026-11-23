import { AlertTriangle, DatabaseZap, FolderX, Wrench } from "lucide-react"

import { Badge } from "@workspace/ui/primitives/badge"
import { cn } from "@workspace/ui/lib/utils"

type BackupUnavailableNoticeProps = {
  /** Abstraction over the two independent prerequisites reported by the API. */
  toolsAvailable: boolean
  storageReady: boolean
  className?: string
}

type Blocker = {
  key: string
  icon: React.ComponentType<{ className?: string }>
  title: string
  detail: string
  remedy: string
}

const TOOL_BLOCKER: Blocker = {
  key: "tools",
  icon: Wrench,
  title: "ابزارهای PostgreSQL نصب نیستند",
  detail:
    "سرور به ابزارهای pg_dump / pg_restore دسترسی ندارد، بنابراین ساخت و بازیابی نسخه ممکن نیست.",
  remedy:
    "بستهٔ postgresql-client را روی سرور نصب و سرویس API را راه اندازی مجدد کنید.",
}

const STORAGE_BLOCKER: Blocker = {
  key: "storage",
  icon: FolderX,
  title: "پوشه ذخیره پشتیبان قابل نوشتن نیست",
  detail:
    "مسیر ذخیره نسخه‌ها وجود ندارد یا حساب سرویس اجازه نوشتن در آن را ندارد.",
  remedy:
    "دسترسی نوشتن پوشه پشتیبان را برای کاربر سرویس فراهم و تنظیمات را بررسی کنید.",
}

/** Distinguishes the active prerequisites so the notice explains exactly what is blocking backups. */
export function BackupUnavailableNotice({
  toolsAvailable,
  storageReady,
  className,
}: BackupUnavailableNoticeProps) {
  const blockers: Blocker[] = []
  if (!toolsAvailable) blockers.push(TOOL_BLOCKER)
  if (!storageReady) blockers.push(STORAGE_BLOCKER)

  if (blockers.length === 0) return null

  return (
    <section
      aria-label="قابلیت پشتیبان گیری در دسترس نیست"
      className={cn(
        "rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4 ring-1 ring-amber-500/10 sm:p-5",
        className
      )}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/15 text-amber-700 dark:text-amber-300">
          <DatabaseZap className="size-6" aria-hidden="true" />
        </div>

        <div className="min-w-0 flex-1 space-y-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-foreground">
                پشتیبان گیری در حال حاضر در دسترس نیست
              </h3>
              <Badge variant="warning" className="gap-1">
                <AlertTriangle className="size-3" aria-hidden="true" />
                نیاز به اقدام سرور
              </Badge>
            </div>
            <p className="text-sm leading-6 text-muted-foreground">
              پیشنیازهای اجرای پشتیبان روی این سرور برآورده نشده است. تا رفع
              مورد زیر، ساخت نسخه، بازیابی و پشتیبان خودکار متوقف هستند.
            </p>
          </div>

          <ul className="space-y-3">
            {blockers.map((blocker) => {
              const Icon = blocker.icon
              return (
                <li
                  key={blocker.key}
                  className="rounded-xl border bg-card/80 p-3 ring-1 ring-foreground/5"
                >
                  <div className="flex items-start gap-3">
                    <Icon
                      className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-300"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-medium text-foreground">
                        {blocker.title}
                      </p>
                      <p className="text-sm leading-6 text-muted-foreground">
                        {blocker.detail}
                      </p>
                      <p className="text-xs leading-6 text-muted-foreground">
                        <span className="font-medium text-foreground">
                          راه حل:{" "}
                        </span>
                        {blocker.remedy}
                      </p>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </section>
  )
}
