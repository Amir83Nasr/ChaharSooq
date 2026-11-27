"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { BadgeCheck, Link2, Pin } from "lucide-react"

import { useIsMobile } from "@workspace/ui/hooks/use-mobile"

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
import { ProductCardexPanel } from "./product-cardex"
import { ProductAIAnalysis } from "./product-ai-analysis"
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

/** Panels fade and lift in while their tab activates. */
const TAB_PANEL_CLASS =
  "mt-1 animate-in fade-in-0 slide-in-from-bottom-1 duration-200 ease-out data-[starting-style]:animate-none data-[starting-style]:translate-y-0.5 data-[starting-style]:opacity-0 transition-[opacity,translate] motion-reduce:animate-none motion-reduce:transition-none"

const FRAME_GAP = 12 // gap-3 between the header and the scrollable body
const FRAME_DURATION = 260

/**
 * Lets the desktop dialog hug the active tab's natural height and animates
 * between heights instead of snapping. The frame stays auto-sized; a
 * ResizeObserver on the tab body measures the new height and plays a short
 * height transition, clamped to the dialog's `max-height`.
 *
 * Disabled on mobile: the bottom sheet fills the viewport height there.
 */
function useAnimatedFrameHeight(enabled: boolean) {
  // The dialog renders inside a portal that mounts one commit after the open
  // state flips, so callback refs are what tell the effect the frame exists.
  const [frame, setFrame] = useState<HTMLDivElement | null>(null)
  const [header, setHeader] = useState<HTMLDivElement | null>(null)
  const [content, setContent] = useState<HTMLDivElement | null>(null)
  const animationRef = useRef<Animation | null>(null)

  useEffect(() => {
    if (!enabled || !frame || !header || !content) return

    const popup = frame.parentElement
    const measure = () => {
      const styles = popup ? getComputedStyle(popup) : null
      const padding = styles
        ? Number.parseFloat(styles.paddingTop) +
          Number.parseFloat(styles.paddingBottom)
        : 0
      const maxHeight = styles
        ? Number.parseFloat(styles.maxHeight)
        : Number.NaN
      const natural = header.offsetHeight + FRAME_GAP + content.offsetHeight
      return Number.isFinite(maxHeight)
        ? Math.min(natural, Math.max(0, maxHeight - padding))
        : natural
    }

    // The observer fires after layout, when the frame already has the new
    // height, so the previous target is the only usable start value.
    let previousTarget: number | null = null
    const observer = new ResizeObserver(() => {
      const next = measure()
      const previous = previousTarget
      previousTarget = next
      if (previous === null || Math.abs(next - previous) < 1) return
      animationRef.current?.cancel()
      animationRef.current = frame.animate(
        [{ height: `${previous}px` }, { height: `${next}px` }],
        {
          duration: FRAME_DURATION,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        }
      )
    })
    observer.observe(header)
    observer.observe(content)

    // A viewport resize changes the max-height clamp without resizing the
    // content; keep the baseline in sync so the next switch starts there.
    const handleResize = () => {
      previousTarget = measure()
    }
    window.addEventListener("resize", handleResize)

    return () => {
      observer.disconnect()
      window.removeEventListener("resize", handleResize)
      animationRef.current?.cancel()
      animationRef.current = null
    }
  }, [enabled, frame, header, content])

  return { frameRef: setFrame, headerRef: setHeader, contentRef: setContent }
}

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
  /**
   * Management accounts generate and delete AI reports; every signed-in account
   * can open the tab and read the saved report.
   */
  canManageAI?: boolean
}) {
  const {
    selected,
    onClose,
    onCompetitorChanged,
    canEdit = true,
    canManageAI = false,
  } = props
  const [localProduct, setLocalProduct] = useState<ProductOut | null>(null)
  const [modeBusy, setModeBusy] = useState<Selection | null>(null)
  const [modeError, setModeError] = useState<string | null>(null)
  const [pinBusy, setPinBusy] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  type DetailTab = "cardex" | "analysis" | "links" | "bounds"
  // Cardex is the primary tab and opens by default for every selected product.
  const [activeTab, setActiveTab] = useState<DetailTab>("cardex")
  const scrollAreaRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setLocalProduct(selected)
    setActiveTab("cardex")
  }, [selected])

  // A tab switch should start at the top of the new panel, never inherit the
  // scroll offset of the previous one.
  useEffect(() => {
    if (scrollAreaRef.current) scrollAreaRef.current.scrollTop = 0
  }, [activeTab])

  const product = localProduct ?? selected
  const isMobile = useIsMobile()
  const { frameRef, headerRef, contentRef } = useAnimatedFrameHeight(
    !isMobile && product !== null
  )
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
        <div
          ref={frameRef}
          className="flex min-h-0 flex-1 flex-col gap-3 md:max-h-[calc(96dvh-2.5rem)] md:flex-none"
        >
          <ResponsiveDialogHeader
            ref={headerRef}
            className="shrink-0 gap-1 pe-8"
          >
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
            <div
              ref={scrollAreaRef}
              className="no-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain md:pe-1"
            >
              <div ref={contentRef} className="space-y-3">
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
                  <TabsList
                    variant="line"
                    className="no-scrollbar max-w-full self-start overflow-x-auto"
                  >
                    <TabsTrigger value="cardex">کارتکس کالا</TabsTrigger>
                    <TabsTrigger value="analysis">تحلیل هوش مصنوعی</TabsTrigger>
                    <TabsTrigger value="links">لینک فروشگاه‌ها</TabsTrigger>
                    <TabsTrigger value="bounds">
                      محدودیت قیمت پیشنهادی
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="cardex" className={TAB_PANEL_CLASS}>
                    <ProductCardexPanel productId={product.id} />
                  </TabsContent>
                  <TabsContent
                    value="analysis"
                    keepMounted
                    className={TAB_PANEL_CLASS}
                  >
                    {/* Keyed by product so switching products starts clean;
                    keepMounted preserves a finished report across tabs. */}
                    <ProductAIAnalysis
                      key={product.id}
                      productId={product.id}
                      productName={product.name}
                      canManage={canManageAI}
                    />
                  </TabsContent>
                  <TabsContent value="links" className={TAB_PANEL_CLASS}>
                    {linksPanel()}
                  </TabsContent>
                  <TabsContent value="bounds" className={TAB_PANEL_CLASS}>
                    {boundsPanel()}
                  </TabsContent>
                </Tabs>
              </div>
            </div>
          ) : null}
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  )
}
