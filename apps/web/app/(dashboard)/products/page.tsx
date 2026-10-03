"use client"

import { useEffect, useState } from "react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { EmptyState, ErrorState } from "@workspace/ui/components/state"
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
        <ErrorState title="خطا در بارگذاری محصولات" hint={error} />
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
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">نام</TableHead>
              <TableHead scope="col">کد</TableHead>
              <TableHead scope="col">قیمت</TableHead>
              <TableHead scope="col">موجودی</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.name}</TableCell>
                <TableCell>{item.sku}</TableCell>
                <TableCell>
                  <Price value={item.price} />
                </TableCell>
                <TableCell>
                  <PersianNumber value={item.stock} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </>
  )
}
