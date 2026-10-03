"use client"

import { useEffect, useState } from "react"

import { EmptyState } from "@workspace/ui/components/state"
import { PageHeader } from "@workspace/ui/components/page-header"
import { Price } from "@workspace/ui/components/price"
import { PersianNumber } from "@workspace/ui/components/persian-number"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { api, type ProductPage } from "@/lib/api"

export default function ProductsPage() {
  const [page, setPage] = useState<ProductPage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .products({ page_size: 20 })
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "خطایی رخ داد.")
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <PageHeader title="محصولات" subtitle="مدیریت کالاهای فروشگاه" />
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {!page && !error ? (
        <div className="flex flex-col gap-2" aria-label="در حال بارگذاری">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : null}
      {page && page.items.length === 0 ? (
        <EmptyState
          title="محصولی ثبت نشده است"
          hint="اولین محصول را از طریق API اضافه کنید."
        />
      ) : null}
      {page && page.items.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-160 text-sm">
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  نام
                </th>
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  کد
                </th>
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  قیمت
                </th>
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  موجودی
                </th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-border last:border-0"
                >
                  <td className="px-4 py-2">{item.name}</td>
                  <td className="px-4 py-2">{item.sku}</td>
                  <td className="px-4 py-2">
                    <Price value={item.price} />
                  </td>
                  <td className="px-4 py-2">
                    <PersianNumber value={item.stock} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  )
}
