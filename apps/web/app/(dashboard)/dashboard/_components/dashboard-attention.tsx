import Link from "next/link"

import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"
import { buttonVariants } from "@workspace/ui/primitives/button"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"

import type { Attention, AttentionItem } from "@/lib/api"

function AttentionRows({
  items,
  dotClass,
  showStock,
}: {
  items: AttentionItem[]
  dotClass: string
  showStock: boolean
}) {
  return (
    <ul className="flex flex-col">
      {items.map((item) => (
        <li
          key={item.product_id}
          className="flex items-center gap-2 border-b py-2 text-sm first:pt-0 last:border-0 last:pb-0"
        >
          <span
            aria-hidden="true"
            className={`size-2 shrink-0 rounded-full ${dotClass}`}
          />
          <p className="min-w-0 flex-1 truncate">{item.name}</p>
          {showStock ? (
            <span className="shrink-0 text-xs text-muted-foreground">
              <PersianNumber value={item.stock} /> قلم
            </span>
          ) : null}
          <Price
            value={item.price}
            className="shrink-0 text-xs font-semibold"
          />
        </li>
      ))}
    </ul>
  )
}

export function AttentionCard({ attention }: { attention: Attention }) {
  const empty = attention.out.length === 0 && attention.low.length === 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>نیازمند توجه</CardTitle>
        <CardAction>
          <Link
            href="/products"
            className={buttonVariants({ variant: "ghost", size: "sm" })}
          >
            مشاهده محصولات
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {empty ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            موردی برای رسیدگی وجود ندارد.
          </p>
        ) : (
          <>
            {attention.out.length > 0 ? (
              <section aria-label="ناموجودها">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  ناموجود
                </p>
                <AttentionRows
                  items={attention.out}
                  dotClass="bg-rose-500"
                  showStock={false}
                />
              </section>
            ) : null}
            {attention.low.length > 0 ? (
              <section aria-label="موجودی کم">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  موجودی کم
                </p>
                <AttentionRows
                  items={attention.low}
                  dotClass="bg-amber-500"
                  showStock
                />
              </section>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}
