"use client"

import { useState } from "react"
import { ListFilter, X } from "lucide-react"

import { Button } from "@workspace/ui/primitives/button"
import { Badge } from "@workspace/ui/primitives/badge"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@workspace/ui/primitives/drawer"
import { SearchInput } from "@/components/data/data-table-toolbar"
import { ProductsToolbar } from "./products-toolbar"
import type { ProductSort } from "@/lib/api"
import type { CompetitorMarket } from "./products-table"
import type { StockFilter } from "./products-toolbar"

interface Props {
  q: string
  topGroup: string | null
  sort: ProductSort
  stock: StockFilter
  market: CompetitorMarket
  minPrice: string
  maxPrice: string
  hasFilters: boolean
  activeCount: number
  onQ: (v: string) => void
  onTopGroup: (v: string | null) => void
  onSort: (v: ProductSort) => void
  onStock: (v: StockFilter) => void
  onMarketChange: (v: CompetitorMarket) => void
  onMinPrice: (v: string) => void
  onMaxPrice: (v: string) => void
  onClear: () => void
}

export function ProductsMobileFilters(props: Props) {
  const { q, onQ, hasFilters, activeCount, onClear } = props
  const [open, setOpen] = useState(false)

  return (
    // Not sticky: the search row scrolls away with the content (per design).
    <div className="-mx-4 border-b border-border/60 bg-background/85 px-4 pt-1 pb-2 backdrop-blur-md supports-[backdrop-filter]:bg-background/70 md:hidden">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <SearchInput
            value={q}
            onChange={onQ}
            placeholder="جست‌وجو در نام یا کد…"
            aria-label="جست‌وجو در محصولات"
            className="h-11 rounded-2xl"
          />
        </div>
        <Drawer open={open} onOpenChange={setOpen} showSwipeHandle>
          <DrawerTrigger
            render={
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={
                  activeCount > 0
                    ? `باز کردن فیلترها، ${activeCount} فیلتر فعال`
                    : "باز کردن فیلترها"
                }
                className="relative size-11 shrink-0 rounded-2xl"
              >
                <ListFilter className="size-5" aria-hidden="true" />
                {activeCount > 0 ? (
                  <Badge
                    variant="default"
                    aria-hidden="true"
                    className="absolute -start-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full p-0 text-[11px]"
                  >
                    <PersianNumber value={activeCount} />
                  </Badge>
                ) : null}
              </Button>
            }
          />
          <DrawerContent
            aria-label="فیلترهای محصولات"
            className="max-h-[92dvh]"
          >
            <DrawerHeader className="text-start">
              <DrawerTitle>فیلترها و مرتب‌سازی</DrawerTitle>
              <DrawerDescription>
                فیلترها را انتخاب کنید؛ نتیجه خودکار به‌روز می‌شود.
              </DrawerDescription>
            </DrawerHeader>
            <div className="min-h-0 overflow-y-auto px-1 pb-1">
              <ProductsToolbar
                q={q}
                topGroup={props.topGroup}
                sort={props.sort}
                stock={props.stock}
                market={props.market}
                minPrice={props.minPrice}
                maxPrice={props.maxPrice}
                hasFilters={hasFilters}
                onQ={onQ}
                onTopGroup={props.onTopGroup}
                onSort={props.onSort}
                onStock={props.onStock}
                onMarketChange={props.onMarketChange}
                onMinPrice={props.onMinPrice}
                onMaxPrice={props.onMaxPrice}
                onClear={onClear}
              />
            </div>
            <DrawerFooter className="flex-row gap-2 border-t border-border pt-3 pb-[env(safe-area-inset-bottom)]">
              {hasFilters ? (
                <Button
                  type="button"
                  variant="outline"
                  className="h-11 flex-1 rounded-2xl"
                  onClick={onClear}
                >
                  <X aria-hidden="true" />
                  پاک‌سازی
                </Button>
              ) : null}
              <DrawerClose
                render={
                  <Button type="button" className="h-11 flex-1 rounded-2xl">
                    مشاهده نتیجه
                  </Button>
                }
              />
            </DrawerFooter>
          </DrawerContent>
        </Drawer>
      </div>
    </div>
  )
}
