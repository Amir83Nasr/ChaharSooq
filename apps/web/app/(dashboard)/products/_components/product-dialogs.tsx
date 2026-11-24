"use client"

import { useCallback, useEffect, useState } from "react"
import { BadgeCheck, Link2, Pin } from "lucide-react"

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
import { cn } from "@workspace/ui/lib/utils"
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
  icon: typeof Link2
}[] = [
  {
    value: "exact_competitor",
    label: "قیمت رقیب",
    description: "ترکیب وزنی قیمت رقیب دقیق با قیمت پایه",
    icon: Link2,
  },
  {
    value: "similar_product",
    label: "محصول مشابه",
    description: "استفاده از تغییر روزانه قیمت محصول مشابه",
    icon: BadgeCheck,
  },
]
const PIN_ERROR = "تغییر پین انجام نشد. دوباره تلاش کنید."

function toPersianError(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message
  return fallback
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
  const [pinBusy, setPinBusy] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  type DetailTab = "links" | "bounds"
  const [activeTab, setActiveTab] = useState<DetailTab>("links")

  useEffect(() => {
    setLocalProduct(selected)
  }, [selected])

  const product = localProduct ?? selected
  const selection: Selection | null = product ? product.pricing_mode : null
  // Manual rows have no Parsina group; they behave like appliances (the
  // default section) so their competitor links stay manageable.
  const topGroup = product ? (product.top_group ?? "لوازم خانگی") : null

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

    try {
      await api.setPricingMode(previous.id, next)
      onCompetitorChanged?.()
    } catch (err) {
      setLocalProduct(previous)
      setModeError(
        toPersianError(
          err,
          "تغییر حالت قیمت\u200cگذاری انجام نشد. دوباره تلاش کنید."
        )
      )
    } finally {
      setModeBusy(null)
    }
  }

  async function togglePin() {
    if (!product || pinBusy) return
    const previous = product
    const next = !previous.pinned
    setPinError(null)
    setPinBusy(true)
    // Optimistic update, mirroring the pricing-mode selector.
    setLocalProduct({ ...previous, pinned: next })
    try {
      await api.setProductPin(previous.id, { pinned: next })
      onCompetitorChanged?.()
    } catch (err) {
      setLocalProduct(previous)
      setPinError(toPersianError(err, PIN_ERROR))
    } finally {
      setPinBusy(false)
    }
  }

  /** Only the active tab is mounted, so link fetches never duplicate. */
  function linksPanel() {
    if (!product || !topGroup) return null
    return (
      <ProductCompetitorPrices
        productId={product.id}
        stores={storesForTopGroup(topGroup)}
        onChanged={onCompetitorChanged}
        onListingsChanged={handleListingsChanged}
        canEdit={canEdit}
      />
    )
  }

  function boundsPanel() {
    if (!product) return null
    return (
      <div className="grid min-h-0 gap-3 md:grid-cols-2 md:items-start">
        <div className="space-y-3">
          <ProductSuggestedPrice product={product} />
          <p className="rounded-2xl border border-border/70 bg-muted/30 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
            کف و سقف، قیمت پیشنهادی را محدود می‌کند؛ خالی گذاشتن هر فیلد یعنی
            بدون محدودیت.
          </p>
        </div>
        <ProductPriceBounds
          product={product}
          canEdit={canEdit}
          onChanged={onCompetitorChanged}
          onSaved={handleBoundsSaved}
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
        className="no-scrollbar max-h-[92dvh] overflow-y-auto overscroll-contain rounded-t-2xl pb-[calc(1rem+env(safe-area-inset-bottom))] sm:max-w-6xl sm:rounded-2xl md:flex md:max-h-[96dvh] md:flex-col md:gap-3 md:overflow-hidden md:p-5"
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
                حالت قیمت‌گذاری و پین
              </legend>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {MODE_BUTTONS.map((option) => {
                  const active = selection === option.value
                  const busy = modeBusy === option.value
                  const Icon = option.icon
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant="outline"
                      aria-pressed={active}
                      disabled={!canEdit || modeBusy !== null}
                      onClick={() => void selectMode(option.value)}
                      className={cn(
                        "relative h-auto min-h-20 flex-col items-start justify-start gap-1 rounded-2xl border p-3 text-start transition-[background-color,border-color,box-shadow,opacity]",
                        active
                          ? "border-primary/50 bg-primary/5 shadow-[0_0_0_1px_var(--primary)]"
                          : "border-border/70 bg-background/60 opacity-75 hover:opacity-100"
                      )}
                    >
                      <span className="flex w-full items-center gap-2">
                        <span
                          className={cn(
                            "flex size-8 shrink-0 items-center justify-center rounded-xl",
                            active
                              ? "bg-primary/15 text-primary"
                              : "bg-muted text-muted-foreground"
                          )}
                        >
                          <Icon className="size-4" aria-hidden="true" />
                        </span>
                        <BusyLabel
                          busy={busy}
                          idle={option.label}
                          busyLabel={option.label}
                          spinner
                        />
                        {active && !busy ? (
                          <BadgeCheck
                            className="ms-auto size-4 shrink-0 text-primary"
                            aria-label="انتخابشده"
                          />
                        ) : null}
                      </span>
                      <span className="w-full text-[11px] leading-4 font-normal text-muted-foreground">
                        {option.description}
                      </span>
                    </Button>
                  )
                })}
                <Button
                  type="button"
                  variant="outline"
                  aria-pressed={product.pinned}
                  disabled={!canEdit || modeBusy !== null || pinBusy}
                  onClick={() => void togglePin()}
                  className={cn(
                    "relative h-auto min-h-20 flex-col items-start justify-start gap-1 rounded-2xl border p-3 text-start transition-[background-color,border-color,box-shadow,opacity]",
                    product.pinned
                      ? "border-primary/50 bg-primary/5 shadow-[0_0_0_1px_var(--primary)]"
                      : "border-border/70 bg-background/60 opacity-75 hover:opacity-100"
                  )}
                >
                  <span className="flex w-full items-center gap-2">
                    <span
                      className={cn(
                        "flex size-8 shrink-0 items-center justify-center rounded-xl",
                        product.pinned
                          ? "bg-primary/15 text-primary"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      <Pin className="size-4" aria-hidden="true" />
                    </span>
                    <BusyLabel
                      busy={pinBusy}
                      idle={product.pinned ? "پین\u200cشده" : "پین"}
                      busyLabel={product.pinned ? "پین\u200cشده" : "پین"}
                      spinner
                    />
                    {product.pinned && !pinBusy ? (
                      <BadgeCheck
                        className="ms-auto size-4 shrink-0 text-primary"
                        aria-label="انتخابشده"
                      />
                    ) : null}
                  </span>
                  <span className="w-full text-[11px] leading-4 font-normal text-muted-foreground">
                    نگه داشتن کالا برای بررسی بعدی
                  </span>
                </Button>
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

            {pinError ? (
              <p
                role="alert"
                className="rounded-2xl border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
              >
                {pinError}
              </p>
            ) : null}

            <Tabs
              value={activeTab}
              onValueChange={(value) => setActiveTab(value as DetailTab)}
              className="gap-2"
            >
              <TabsList variant="line" className="self-start">
                <TabsTrigger value="links">لینک فروشگاه‌ها</TabsTrigger>
                <TabsTrigger value="bounds">محدودیت قیمت پیشنهادی</TabsTrigger>
              </TabsList>
              <TabsContent value="links" className="mt-1">
                {linksPanel()}
              </TabsContent>
              <TabsContent value="bounds" className="mt-1">
                {boundsPanel()}
              </TabsContent>
            </Tabs>
          </div>
        ) : null}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
