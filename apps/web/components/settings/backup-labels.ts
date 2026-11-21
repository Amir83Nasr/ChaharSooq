/* Persian labels for backup/restore machine values.

   Codes come from the API (`error_code`) and are stable; the UI owns their
   wording so a failure never surfaces raw English client output. */

import type { BackupKind } from "@/lib/api"

export const BACKUP_KIND_LABELS: Record<BackupKind, string> = {
  scheduled: "خودکار",
  operator: "دستی",
  uploaded: "بارگذاری‌شده",
  pre_restore: "پیش از بازیابی",
}

const BACKUP_ERROR_LABELS: Record<string, string> = {
  dump_failed: "ساخت فایل پشتیبان ناموفق بود.",
  dump_timeout: "ساخت پشتیبان بیش از حد طول کشید و متوقف شد.",
  archive_invalid: "فایل، آرشیو معتبر pg_dump نیست.",
  archive_missing: "فایل این پشتیبان روی سرور موجود نیست.",
  restore_failed: "بازیابی ناموفق بود؛ داده‌ها به حالت قبل بازگشت.",
  restore_timeout: "بازیابی بیش از حد طول کشید و متوقف شد.",
  pg_tools_unavailable: "ابزارهای PostgreSQL روی این سرور نصب نیستند.",
  pre_restore_failed: "ساخت پشتیبان ایمنی پیش از بازیابی ناموفق بود.",
  interrupted: "اجرا پیش از پایان متوقف شد.",
  storage_unavailable: "پوشه ذخیره پشتیبان در دسترس یا قابل نوشتن نیست.",
}

export function backupErrorLabel(code: string | null): string | null {
  if (!code) return null
  return BACKUP_ERROR_LABELS[code] ?? "خطای ناشناخته در اجرای پشتیبان‌گیری."
}
