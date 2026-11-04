import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"
import { cn } from "@workspace/ui/lib/utils"

import type { CompetitorGap } from "@/lib/api"

const STORE_LABELS: Record<CompetitorGap["competitor_store"], string> = {
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
  other: "سایر",
}

function gapLabel(diff: number): string {
  if (diff > 0) return "گران‌تر"
  if (diff < 0) return "ارزان‌تر"
  return "هم‌قیمت"
}

export function CompetitorGaps({ gaps }: { gaps: CompetitorGap[] }) {
  const scale = Math.max(1, ...gaps.map((gap) => Math.abs(gap.diff_percent)))
  return (
    <Card>
      <CardHeader>
        <CardTitle>اختلاف قیمت با رقیب</CardTitle>
      </CardHeader>
      <CardContent>
        {gaps.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            قیمت معتبر رقیبی برای مقایسه ثبت نشده است.
          </p>
        ) : (
          <ul className="flex flex-col gap-5">
            {gaps.map((gap) => {
              const width = `${Math.max(3, (Math.abs(gap.diff_percent) / scale) * 50)}%`
              return (
                <li key={gap.product_id}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="min-w-0 truncate text-sm font-medium">
                      {gap.name}
                    </p>
                    <span
                      className={cn(
                        "shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold",
                        gap.diff_percent > 0 &&
                          "bg-rose-500/10 text-rose-600 dark:text-rose-500",
                        gap.diff_percent < 0 &&
                          "bg-emerald-500/10 text-emerald-600 dark:text-emerald-500",
                        gap.diff_percent === 0 &&
                          "bg-muted text-muted-foreground"
                      )}
                    >
                      <PersianNumber value={Math.abs(gap.diff_percent)} />٪{" "}
                      {gapLabel(gap.diff_percent)}
                    </span>
                  </div>
                  <div
                    className="relative mt-1.5 h-2 overflow-hidden rounded-full bg-muted/60"
                    role="img"
                    aria-label={`${gap.name}: ${gap.diff_percent} درصد ${gapLabel(gap.diff_percent)}`}
                  >
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-0 start-1/2 w-px bg-border"
                    />
                    <div
                      aria-hidden="true"
                      className={cn(
                        "absolute inset-y-0 rounded-full",
                        gap.diff_percent > 0 && "bg-rose-500",
                        gap.diff_percent < 0 && "bg-emerald-500",
                        gap.diff_percent === 0 && "bg-muted-foreground/40"
                      )}
                      style={
                        gap.diff_percent >= 0
                          ? { insetInlineStart: "50%", width }
                          : { insetInlineEnd: "50%", width }
                      }
                    />
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span>
                      ما: <Price value={gap.our_price} />
                    </span>
                    <span>
                      {STORE_LABELS[gap.competitor_store]}:{" "}
                      <Price value={gap.competitor_price} />
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
