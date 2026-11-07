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
        className="no-scrollbar max-h-[90dvh] overflow-y-auto rounded-t-2xl pb-[calc(1rem+env(safe-area-inset-bottom))] sm:max-w-5xl sm:rounded-2xl sm:pb-6"
      >
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{product?.name ?? ""}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {product ? `کد کالا: ${product.sku}` : ""}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {product ? (
          <div className="no-scrollbar min-h-0 space-y-4 overflow-y-auto">
            <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-2xl border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">موجودی</dt>
                <dd className="mt-0.5 font-semibold">
                  <PersianNumber value={product.stock} /> عدد
                </dd>
              </div>
              <div className="rounded-2xl border border-border px-3 py-2">
                <dt className="text-xs text-muted-foreground">قیمت</dt>
                <dd className="mt-0.5 font-semibold">
                  <Price value={product.price} />
                </dd>
              </div>
            </dl>
            <ProductSuggestedPrice product={product} />
            {topGroup ? (
              <ProductCompetitorPrices
                productId={product.id}
                stores={DIALOG_STORES[topGroup]}
                onChanged={onCompetitorChanged}
                onListingsChanged={handleListingsChanged}
                canEdit={canEdit}
              />
            ) : null}
            <ProductPriceBounds
              product={product}
              canEdit={canEdit}
              onChanged={onCompetitorChanged}
              onSaved={handleBoundsSaved}
            />
          </div>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
