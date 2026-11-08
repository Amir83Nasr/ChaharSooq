"use client"

import { useCallback, useEffect, useState } from "react"

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/primitives/responsive-dialog"
import { Price } from "@workspace/ui/persian/price"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import type {
  CompetitorListing,
  CompetitorPrice,
  ProductOut,
  TopGroup,
} from "@/lib/api"
import {
  DIALOG_STORES,
  ProductCompetitorPrices,
} from "./product-competitor-prices"
import { ProductPriceBounds } from "./product-price-bounds"
import { ProductSuggestedPrice } from "./product-suggested-price"

function topGroupOf(name: string | null): TopGroup {
  const value = name?.trim() ?? ""
  if (value.startsWith("فرش")) return "فرش"
  if (value.startsWith("مبلمان")) return "مبلمان"
  return "لوازم خانگی"
}

/** Dialog listings carry the same price facts the table receives. */
function listingToPrice(listing: CompetitorListing): CompetitorPrice {
  return {
    id: listing.id,
    store: listing.store,
    url: listing.url,
    status: listing.status,
    price: listing.effective_price,
    currency: listing.effective_currency,
    in_stock: listing.effective_in_stock,
    is_fresh: listing.price_is_fresh,
    is_manual:
      listing.price_is_fresh &&
      listing.manual_price !== null &&
      listing.effective_price === listing.manual_price,
    last_checked_at: listing.last_checked_at,
    price_change_percent: listing.price_change_percent,
    previous_price: listing.previous_price,
    previous_currency: listing.previous_currency,
    previous_observed_at: listing.previous_observed_at,
  }
}

export function ProductDetailDialog(props: {
  selected: ProductOut | null
  onClose: () => void
  onCompetitorChanged?: () => void
  /** `false` for read-only accounts: prices stay visible, editing is hidden. */
  canEdit?: boolean
}) {
  const { selected, onClose, onCompetitorChanged, canEdit = true } = props
  const [localProduct, setLocalProduct] = useState<ProductOut | null>(null)

  useEffect(() => {
    setLocalProduct(selected)
  }, [selected])

  const product = localProduct ?? selected
  const topGroup = product ? topGroupOf(product.main_group_name) : null

  const handleListingsChanged = useCallback((listings: CompetitorListing[]) => {
    setLocalProduct((current) =>
      current
        ? { ...current, competitor_prices: listings.map(listingToPrice) }
        : current
    )
  }, [])

  const handleBoundsSaved = useCallback((updated: ProductOut) => {
    setLocalProduct((current) =>
      current
        ? {
            ...current,
            allowed_decrease_percent: updated.allowed_decrease_percent,
            allowed_increase_percent: updated.allowed_increase_percent,
          }
        : current
    )
  }, [])

  return (
    <ResponsiveDialog
      open={selected !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <ResponsiveDialogContent
        aria-label="جزئیات کالا"
        className="no-scrollbar max-h-[92dvh] overflow-y-auto overscroll-contain rounded-t-2xl pb-[calc(1rem+env(safe-area-inset-bottom))] sm:max-w-5xl sm:rounded-2xl md:flex md:max-h-[96dvh] md:flex-col md:gap-3 md:overflow-hidden md:p-5"
      >
        <ResponsiveDialogHeader className="shrink-0 gap-1 pe-8">
          <ResponsiveDialogTitle>{product?.name ?? ""}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {product ? (
              <>
                <span>کد کالا: {product.sku}</span>
                <span aria-hidden="true" className="text-border">
                  ·
                </span>
                <span>
                  موجودی: <PersianNumber value={product.stock} /> عدد
                </span>
                <span aria-hidden="true" className="text-border">
                  ·
                </span>
                <span>
                  قیمت فعلی:{" "}
                  <Price
                    value={product.price}
                    className="font-medium text-foreground"
                  />
                </span>
              </>
            ) : null}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {product ? (
          <div className="no-scrollbar min-h-0 space-y-3 md:grid md:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] md:items-start md:gap-3 md:space-y-0 md:overflow-y-auto md:pe-1">
            <div className="space-y-3">
              <ProductSuggestedPrice product={product} />
              <ProductPriceBounds
                product={product}
                canEdit={canEdit}
                onChanged={onCompetitorChanged}
                onSaved={handleBoundsSaved}
              />
            </div>
            {topGroup ? (
              <ProductCompetitorPrices
                productId={product.id}
                stores={DIALOG_STORES[topGroup]}
                onChanged={onCompetitorChanged}
                onListingsChanged={handleListingsChanged}
                canEdit={canEdit}
              />
            ) : null}
          </div>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
