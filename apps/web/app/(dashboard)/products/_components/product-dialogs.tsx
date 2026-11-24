"use client"

import { useCallback, useEffect, useState } from "react"

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from "@workspace/ui/primitives/responsive-dialog"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/primitives/tabs"
import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import { Price } from "@workspace/ui/persian/price"
import { PersianNumber } from "@workspace/ui/persian/persian-number"
import {
  ApiRequestError,
  api,
  type CompetitorListing,
  type CompetitorPrice,
  type PricingMode,
  type ProductOut,
} from "@/lib/api"
import { ProductCompetitorPrices } from "./product-competitor-prices"
import { storesForTopGroup } from "@/lib/top-groups"
import { ProductPriceBounds } from "./product-price-bounds"
import { ProductSuggestedPrice } from "./product-suggested-price"

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

type Selection = PricingMode

const MODE_BUTTONS: {
  value: Selection
  label: string
  description: string
}[] = [
  {
    value: "exact_competitor",
    label: "قیمت رقیب",
    description: "ترکیب وزنی قیمت رقیب دقیق با قیمت پایه",
  },
  {
    value: "similar_product",
    label: "محصول مشابه",
    description: "استفاده از تغییر روزانه قیمت محصول مشابه",
  },
  {
    value: "no_competitor_price",
    label: "فاقد قیمت رقیب",
    description: "غیرفعال کردن لینک‌ها و ستون‌های رقیب",
  },
]

function toPersianError(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "تغییر حالت قیمت‌گذاری انجام نشد. دوباره تلاش کنید."
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
  const [modeBusy, setModeBusy] = useState<Selection | null>(null)
  const [modeError, setModeError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<PricingMode>("exact_competitor")

  useEffect(() => {
    setLocalProduct(selected)
  }, [selected])

  const product = localProduct ?? selected
  const selection: Selection | null = product ? product.pricing_mode : null
  // Manual rows have no Parsina group; they behave like appliances (the
  // default section) so their competitor links stay manageable.
  const topGroup = product ? (product.top_group ?? "لوازم خانگی") : null

  // Keep the visible tab in sync with the product's mode (also on dialog open
  // and after an optimistic mode change).
  useEffect(() => {
    if (product && product.pricing_mode !== "no_competitor_price") {
      setActiveTab(product.pricing_mode)
    }
  }, [product?.id, product?.pricing_mode])

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

  async function selectMode(next: Selection) {
    if (!product || selection === next || modeBusy !== null) return
    const previous = product
    setModeError(null)
    setModeBusy(next)

    // Optimistic update: derived selection and tab switch immediately.
    setLocalProduct({ ...previous, pricing_mode: next })
    if (next !== "no_competitor_price") setActiveTab(next)

    try {
      await api.setPricingMode(previous.id, next)
      onCompetitorChanged?.()
    } catch (err) {
      setLocalProduct(previous)
      if (previous.pricing_mode !== "no_competitor_price") {
        setActiveTab(previous.pricing_mode)
      }
      setModeError(toPersianError(err))
    } finally {
      setModeBusy(null)
    }
  }

  /** One tab's content; only the active tab is mounted to avoid duplicate fetches. */
  function modePanel() {
    if (!product || !topGroup) return null
    return (
      <div className="grid min-h-0 gap-3 md:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] md:items-start">
        <div className="space-y-3">
          <ProductSuggestedPrice product={product} />
          <ProductPriceBounds
            product={product}
            canEdit={canEdit}
            onChanged={onCompetitorChanged}
            onSaved={handleBoundsSaved}
          />
        </div>
        <ProductCompetitorPrices
          productId={product.id}
          stores={storesForTopGroup(topGroup)}
          onChanged={onCompetitorChanged}
          onListingsChanged={handleListingsChanged}
          canEdit={canEdit}
        />
      </div>
    )
  }

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
          <div className="no-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain md:pe-1">
            <fieldset
              disabled={!canEdit || modeBusy !== null}
              className="min-w-0 space-y-2 rounded-2xl border border-border/70 bg-muted/30 p-2.5 disabled:opacity-70"
            >
              <legend className="px-1 text-xs font-medium text-muted-foreground">
                حالت قیمت‌گذاری
              </legend>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {MODE_BUTTONS.map((option) => {
                  const active = selection === option.value
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={active ? "secondary" : "outline"}
                      aria-pressed={active}
                      disabled={!canEdit || modeBusy !== null}
                      onClick={() => void selectMode(option.value)}
                      className="h-auto min-h-11 flex-col items-start gap-0.5 rounded-2xl px-3 py-2 text-start"
                    >
                      <BusyLabel
                        busy={modeBusy === option.value}
                        idle={option.label}
                        busyLabel={option.label}
                        spinner
                      />
                      <span className="w-full text-[11px] leading-4 font-normal text-muted-foreground">
                        {option.description}
                      </span>
                    </Button>
                  )
                })}
              </div>
            </fieldset>

            {modeError ? (
              <p
                role="alert"
                className="rounded-2xl border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
              >
                {modeError}
              </p>
            ) : null}

            {selection === "no_competitor_price" ? (
              // No tabs in this mode: links are suppressed, so a notice is
              // clearer than two tabs of dead controls. The three-way selector
              // above switches back to an active mode.
              <div className="space-y-3">
                <ProductSuggestedPrice product={product} />
                <p className="rounded-2xl border border-dashed border-border bg-background px-3 py-4 text-center text-xs leading-6 text-muted-foreground">
                  این کالا فاقد قیمت رقیب است. برای ویرایش لینک‌ها، حالت «قیمت
                  رقیب» یا «محصول مشابه» را انتخاب کنید.
                </p>
              </div>
            ) : (
              <Tabs
                value={activeTab}
                onValueChange={(value) => setActiveTab(value as PricingMode)}
                className="gap-2"
              >
                <TabsList variant="line" className="self-start">
                  <TabsTrigger value="exact_competitor">قیمت رقیب</TabsTrigger>
                  <TabsTrigger value="similar_product">محصول مشابه</TabsTrigger>
                </TabsList>
                <TabsContent value="exact_competitor" className="mt-1">
                  {modePanel()}
                </TabsContent>
                <TabsContent value="similar_product" className="mt-1">
                  {modePanel()}
                </TabsContent>
              </Tabs>
            )}
          </div>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
