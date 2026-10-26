import { toPersianDigits } from "@workspace/ui/lib/number"

import type { SyncStatus } from "./api"

/** One-line outcome of the last finished run. Source values stay numeric. */
export function syncSummaryMessage(status: SyncStatus): string {
  const parts = [`${toPersianDigits(status.last_processed)} کالا بررسی شد`]
  if (status.last_created > 0)
    parts.push(`${toPersianDigits(status.last_created)} کالای جدید`)
  if (status.last_updated > 0)
    parts.push(`${toPersianDigits(status.last_updated)} کالا به‌روز شد`)
  if (status.last_deactivated > 0)
    parts.push(`${toPersianDigits(status.last_deactivated)} کالا غیرفعال شد`)
  if (status.last_skipped > 0)
    parts.push(`${toPersianDigits(status.last_skipped)} کالا رد شد`)
  return parts.join("، ")
}
