"use client"

import { useState } from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/primitives/table"
import { Button } from "@workspace/ui/primitives/button"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import { Price } from "@workspace/ui/persian/price"

import type { CatalogSection } from "@/lib/api"

const INITIAL_BRAND_ROWS = 6

function SectionSummary({ section }: { section: CatalogSection }) {
  return (
    <div className="rounded-2xl border bg-muted/40 p-4">
      <p className="text-sm font-semibold">{section.top_group}</p>
      <p className="mt-2 text-2xl font-bold">
        <PersianNumber value={section.items} />
        <span className="ms-1 text-xs font-normal text-muted-foreground">
          قلم کالا
        </span>
      </p>
      <div className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
        <p>
          <PersianNumber value={section.group_count} /> دسته
          <span className="mx-1" aria-hidden="true">
            ·
          </span>
          <PersianNumber value={section.brand_count} /> برند
        </p>
        <Price value={section.stock_value} className="text-sm font-semibold" />
      </div>
    </div>
  )
}

function SectionBrands({ section }: { section: CatalogSection }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded
    ? section.brands
    : section.brands.slice(0, INITIAL_BRAND_ROWS)
  return (
    <section aria-label={`برندهای ${section.top_group}`} className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{section.top_group}</h3>
        <p className="text-xs text-muted-foreground">
          <PersianNumber value={section.brand_count} /> برند
          <span className="mx-1" aria-hidden="true">
            ·
          </span>
          <PersianNumber value={section.items} /> قلم
        </p>
      </div>
      {section.brands.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          برندی در این بخش ثبت نشده است.
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-2 md:hidden">
            {visible.map((brand) => (
              <li
                key={brand.group_name}
                className="flex items-center gap-3 rounded-2xl border border-border bg-card px-3 py-2.5"
              >
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-sm font-medium">
                    {brand.brand}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {brand.group_name}
                  </span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-0.5">
                  <span className="text-sm font-bold">
                    <PersianNumber value={brand.count} />
                  </span>
                  <Price
                    value={brand.stock_value}
                    className="text-xs font-medium text-muted-foreground"
                  />
                </span>
              </li>
            ))}
          </ul>
          <div className="hidden overflow-x-auto md:block">
            <Table className="min-w-160">
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">برند</TableHead>
                  <TableHead scope="col">گروه</TableHead>
                  <TableHead scope="col" className="text-center">
                    تعداد اقلام
                  </TableHead>
                  <TableHead scope="col" className="text-center">
                    ارزش موجودی
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((brand) => (
                  <TableRow key={brand.group_name}>
                    <TableCell className="text-sm font-medium">
                      {brand.brand}
                    </TableCell>
                    <TableCell className="max-w-56 truncate text-sm text-muted-foreground">
                      {brand.group_name}
                    </TableCell>
                    <TableCell className="text-center">
                      <PersianNumber value={brand.count} />
                    </TableCell>
                    <TableCell className="text-center">
                      <Price value={brand.stock_value} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {section.brands.length > INITIAL_BRAND_ROWS ? (
            <Button
              variant="outline"
              size="sm"
              className="h-11 w-full rounded-2xl md:h-9 md:w-auto"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "نمایش کمتر" : "نمایش همه برندها"}
            </Button>
          ) : null}
        </>
      )}
    </section>
  )
}

export function CatalogBreakdown({ sections }: { sections: CatalogSection[] }) {
  const visible = sections.filter((s) => s.items > 0 || s.top_group !== "سایر")
  return (
    <Card>
      <CardHeader>
        <CardTitle>آمار بخش‌ها و برندها</CardTitle>
        <CardDescription>
          تعداد دسته‌ها و اقلام هر بخش، برندهای هر بخش و تعداد محصولات هر برند
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {visible.map((section) => (
            <SectionSummary key={section.top_group} section={section} />
          ))}
        </div>
        <div className="flex flex-col gap-6">
          {visible
            .filter((s) => s.items > 0)
            .map((section) => (
              <SectionBrands key={section.top_group} section={section} />
            ))}
        </div>
      </CardContent>
    </Card>
  )
}
