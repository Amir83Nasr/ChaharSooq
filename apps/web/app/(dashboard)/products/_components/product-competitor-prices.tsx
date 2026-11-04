"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ExternalLink,
  LoaderCircle,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react"

import { Badge } from "@workspace/ui/primitives/badge"
import { Button } from "@workspace/ui/primitives/button"
import { Input } from "@workspace/ui/primitives/input"
import { Skeleton } from "@workspace/ui/primitives/skeleton"
import { Price } from "@workspace/ui/persian/price"
import { PersianDateTime } from "@workspace/ui/persian/persian-date"
import { toTomanAmount } from "@/lib/money"
import {
  ApiRequestError,
  api,
  type CompetitorListing,
  type CompetitorStore,
} from "@/lib/api"

/** دو کارت ثابت دیالوگ محصول (فقط لوازم خانگی). */
const DIALOG_STORES: CompetitorStore[] = ["digikala", "technolife"]

const STORE_LABELS: Record<CompetitorStore, string> = {
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
  other: "سایر فروشگاه‌ها",
}

const STORE_URL_PLACEHOLDERS: Record<CompetitorStore, string> = {
  digikala: "https://www.digikala.com/product/dkp-123456/",
  technolife: "https://www.technolife.ir/product-123456/",
  other: "https://example.com/product/123",
}

const STORE_URL_HINTS: Record<CompetitorStore, string> = {
  digikala: "دامنهٔ مجاز: digikala.com",
  technolife: "دامنهٔ مجاز: technolife.ir",
  other: "",
}

function isUrlMatchingStore(url: string, store: CompetitorStore): boolean {
  const raw = url.trim()
  if (!raw) return true
  try {
    const hostname = new URL(raw).hostname.toLowerCase().replace(/\.$/, "")
    if (store === "digikala")
      return hostname === "digikala.com" || hostname === "www.digikala.com"
    if (store === "technolife")
      return (
        hostname === "technolife.ir" ||
        hostname === "www.technolife.ir" ||
        hostname === "technolife.com" ||
        hostname === "www.technolife.com"
      )
    return true
  } catch {
    return true
  }
}

function listingStoreLabel(listing: CompetitorListing): string {
  if (listing.store !== "other") return STORE_LABELS[listing.store]
  try {
    return new URL(listing.url).hostname
  } catch {
    return STORE_LABELS.other
  }
}

const STATUS_LABELS: Record<CompetitorListing["status"], string> = {
  pending: "در انتظار بررسی",
  success: "دریافت شد",
  not_found: "صفحه پیدا نشد",
  unavailable: "استخراج در دسترس نیست",
  blocked: "دسترسی محدود شد",
  failed: "دریافت ناموفق",
  manual: "ثبت دستی",
}

function statusBadgeVariant(
  status: CompetitorListing["status"]
): "default" | "secondary" | "destructive" | "warning" | "outline" {
  switch (status) {
    case "success":
      return "default"
    case "manual":
      return "secondary"
    case "pending":
      return "outline"
    case "blocked":
    case "failed":
      return "destructive"
    default:
      return "warning"
  }
}

function toPersianError(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "عملیات انجام نشد. دوباره تلاش کنید."
}

function FilledSlotCard({
  listing,
  busy,
  onLinkUpdate,
  onCheck,
  onDelete,
}: {
  listing: CompetitorListing
  busy: boolean
  onLinkUpdate: (url: string) => void
  onCheck: (url: string) => void
  onDelete: () => void
}) {
  const [url, setUrl] = useState(listing.url)

  useEffect(() => {
    setUrl(listing.url)
  }, [listing])

  const trimmedUrl = url.trim()
  const urlMismatch =
    trimmedUrl !== "" && !isUrlMatchingStore(trimmedUrl, listing.store)
  const linkDirty = trimmedUrl !== listing.url.trim()
  const canPersist = !busy && !urlMismatch && trimmedUrl !== "" && linkDirty

  function persistLink() {
    const trimmed = url.trim()
    if (!trimmed) return
    if (!isUrlMatchingStore(trimmed, listing.store)) return
    if (trimmed === listing.url.trim()) return
    onLinkUpdate(trimmed)
  }

  function handleUrlBlur() {
    // Only normalise whitespace here; persisting is explicit via the save
    // button so a stray blur cannot PATCH the link by accident.
    setUrl((current) => current.trim())
  }

  return (
    <article className="space-y-3 rounded-lg border border-border bg-background p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{listingStoreLabel(listing)}</Badge>
          <Badge variant={statusBadgeVariant(listing.status)}>
            {STATUS_LABELS[listing.status]}
          </Badge>
          {busy ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <LoaderCircle
                className="size-3.5 animate-spin"
                aria-hidden="true"
              />
              در حال ذخیره…
            </span>
          ) : linkDirty && canPersist ? (
            <span className="text-[11px] text-muted-foreground">
              تغییر ذخیره نشده؛ دکمه «ذخیره لینک» را بزنید
            </span>
          ) : null}
        </div>
        <a
          href={listing.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          مشاهده در فروشگاه
          <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
        </a>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-md bg-muted/50 px-3 py-2">
        <div>
          <p className="text-xs text-muted-foreground">قیمت مؤثر</p>
          {listing.effective_price !== null ? (
            <p className="text-base font-semibold">
              <Price
                value={
                  toTomanAmount(
                    listing.effective_price,
                    listing.effective_currency
                  ) ?? listing.effective_price
                }
              />
              {!listing.price_is_fresh ? (
                <span className="ms-2 text-[11px] font-normal text-muted-foreground">
                  (قدیمی)
                </span>
              ) : null}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              قیمت تازه دریافت نشده
            </p>
          )}
        </div>
        <div>
          <p className="text-xs text-muted-foreground">موجودی</p>
          <p className="text-sm font-medium">
            {listing.effective_in_stock === null
              ? "نامشخص"
              : listing.effective_in_stock
                ? "موجود"
                : "ناموجود"}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">آخرین بررسی</p>
          <p className="text-sm">
            {listing.last_checked_at ? (
              <PersianDateTime value={listing.last_checked_at} />
            ) : (
              "هنوز بررسی نشده"
            )}
          </p>
        </div>
      </div>

      {listing.last_error ? (
        <p role="alert" className="text-xs text-destructive">
          {listing.last_error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">
          لینک صفحهٔ محصول
        </p>
        <div className="min-w-0 space-y-1">
          <Input
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onBlur={handleUrlBlur}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault()
                ;(event.target as HTMLInputElement).blur()
              }
            }}
            placeholder={STORE_URL_PLACEHOLDERS[listing.store]}
            aria-label={`لینک صفحه محصول ${listingStoreLabel(listing)}`}
            aria-invalid={urlMismatch || undefined}
            title={trimmedUrl || undefined}
            dir="ltr"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            inputMode="url"
            className="h-10 w-full min-w-0 text-left text-sm text-ellipsis"
            required
            disabled={busy}
          />
          {STORE_URL_HINTS[listing.store] ? (
            <p className="text-[11px] leading-4 text-muted-foreground">
              {STORE_URL_HINTS[listing.store]}
            </p>
          ) : null}
          {urlMismatch ? (
            <p role="alert" className="text-[11px] leading-4 text-destructive">
              دامنهٔ لینک با فروشگاه انتخاب‌شده هم‌خوانی ندارد.
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={!canPersist}
          onClick={persistLink}
        >
          ذخیره لینک
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={busy || trimmedUrl === "" || urlMismatch}
          onClick={() => onCheck(url.trim())}
        >
          {busy ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}
          بررسی لینک
        </Button>
        <span className="ms-auto flex gap-1">
          <Button
            size="sm"
            variant="destructive"
            disabled={busy}
            onClick={() => {
              if (
                window.confirm("این لینک حذف شود؟ این عمل قابل بازگشت نیست.")
              ) {
                onDelete()
              }
            }}
          >
            <Trash2 /> حذف
          </Button>
        </span>
      </div>
    </article>
  )
}

function EmptySlotCard({
  store,
  busy,
  onCreate,
}: {
  store: CompetitorStore
  busy: boolean
  onCreate: (url: string) => void
}) {
  const [url, setUrl] = useState("")
  const trimmedUrl = url.trim()
  const urlMismatch =
    trimmedUrl !== "" && !isUrlMatchingStore(trimmedUrl, store)

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed || urlMismatch) return
    onCreate(trimmed)
  }

  return (
    <article className="space-y-3 rounded-lg border border-dashed border-border bg-background p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{STORE_LABELS[store]}</Badge>
          <span className="text-[11px] text-muted-foreground">
            لینکی ثبت نشده است
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">
          لینک صفحهٔ محصول {STORE_LABELS[store]} را وارد کنید
        </p>
        <div className="min-w-0 space-y-1">
          <Input
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onBlur={(event) => setUrl(event.target.value.trim())}
            placeholder={STORE_URL_PLACEHOLDERS[store]}
            aria-label={`لینک صفحه محصول ${STORE_LABELS[store]}`}
            aria-invalid={urlMismatch || undefined}
            title={trimmedUrl || undefined}
            dir="ltr"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            inputMode="url"
            className="h-10 w-full min-w-0 text-left text-sm text-ellipsis"
            required
            disabled={busy}
          />
          {STORE_URL_HINTS[store] ? (
            <p className="text-[11px] leading-4 text-muted-foreground">
              {STORE_URL_HINTS[store]}
            </p>
          ) : null}
          {urlMismatch ? (
            <p role="alert" className="text-[11px] leading-4 text-destructive">
              دامنهٔ لینک با فروشگاه انتخاب‌شده هم‌خوانی ندارد.
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="submit"
            size="sm"
            disabled={busy || trimmedUrl === "" || urlMismatch}
          >
            {busy ? <LoaderCircle className="animate-spin" /> : <Plus />}
            ثبت لینک
          </Button>
          {busy ? (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <LoaderCircle
                className="size-3.5 animate-spin"
                aria-hidden="true"
              />
              در حال ذخیره…
            </span>
          ) : null}
        </div>
      </form>
    </article>
  )
}

export function ProductCompetitorPrices({
  productId,
  onChanged,
}: {
  productId: number
  onChanged?: () => void
}) {
  const [listings, setListings] = useState<CompetitorListing[]>([])
  const [loading, setLoading] = useState(true)
  const [busyKey, setBusyKey] = useState<number | string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setListings(await api.competitorListings(productId))
      setError(null)
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setLoading(false)
    }
  }, [productId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function mutate(id: number, action: () => Promise<CompetitorListing>) {
    setBusyKey(id)
    try {
      const updated = await action()
      setListings((current) =>
        current.map((listing) => (listing.id === id ? updated : listing))
      )
      setError(null)
      onChanged?.()
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setBusyKey(null)
    }
  }

  async function createListing(store: CompetitorStore, url: string) {
    const trimmed = url.trim()
    if (!trimmed) return
    setBusyKey(`create-${store}`)
    try {
      const created = await api.createCompetitorListing(
        productId,
        store,
        trimmed
      )
      setListings((current) => [...current, created])
      setError(null)
      onChanged?.()
      // بررسی خودکار دفعهٔ اول در پس‌زمینه: خطای آن داخل کارت (last_error)
      // می‌نشیند و پیام سراسری موفقیت ساخت را خراب نمی‌کند.
      try {
        setBusyKey(created.id)
        const checked = await api.checkCompetitorListing(created.id)
        setListings((current) =>
          current.map((listing) =>
            listing.id === created.id ? checked : listing
          )
        )
        onChanged?.()
      } catch {
        // Refresh so the card shows the fetch status/last_error instead.
        try {
          setListings(await api.competitorListings(productId))
        } catch {
          // Keep the created listing visible; the card will retry on demand.
        }
      } finally {
        setBusyKey(null)
      }
    } catch (err) {
      setError(toPersianError(err))
      setBusyKey(null)
    }
  }

  async function removeListing(id: number) {
    setBusyKey(id)
    try {
      await api.deleteCompetitorListing(id)
      setListings((current) => current.filter((listing) => listing.id !== id))
      setError(null)
      onChanged?.()
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setBusyKey(null)
    }
  }

  const byStore = new Map(listings.map((listing) => [listing.store, listing]))
  const otherListings = listings.filter((listing) => listing.store === "other")

  return (
    <section className="space-y-4 rounded-lg border border-border bg-muted/30 p-4 text-start">
      <div>
        <h3 className="font-semibold">قیمت فروشگاه‌های دیگر</h3>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          برای هر فروشگاه یک کارت وجود دارد. لینک را وارد کنید تا ذخیره و
          به‌صورت خودکار بررسی شود؛ با «بررسی لینک» می‌توانید بعداً قیمت را
          به‌روزرسانی کنید و با «حذف» لینک دستی پاک می‌شود. قیمت فقط تا ۲۴ ساعت
          تازه محسوب می‌شود.
        </p>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {loading ? (
        <div className="space-y-3" aria-label="در حال بارگذاری منابع قیمت">
          {DIALOG_STORES.map((store) => (
            <div
              key={store}
              className="space-y-2 rounded-lg border border-border bg-background p-3 sm:p-4"
            >
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-8 w-28" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {DIALOG_STORES.map((store) => {
            const listing = byStore.get(store)
            if (!listing) {
              return (
                <EmptySlotCard
                  key={store}
                  store={store}
                  busy={busyKey === `create-${store}`}
                  onCreate={(url) => void createListing(store, url)}
                />
              )
            }
            return (
              <FilledSlotCard
                key={listing.id}
                listing={listing}
                busy={busyKey === listing.id}
                onLinkUpdate={(url) =>
                  void mutate(listing.id, () =>
                    api.updateCompetitorListing(listing.id, {
                      store: listing.store,
                      url,
                      is_active: true,
                    })
                  )
                }
                onCheck={(url) =>
                  void mutate(listing.id, async () => {
                    if (url !== listing.url.trim()) {
                      await api.updateCompetitorListing(listing.id, {
                        store: listing.store,
                        url,
                        is_active: true,
                      })
                    }
                    return api.checkCompetitorListing(listing.id)
                  })
                }
                onDelete={() => void removeListing(listing.id)}
              />
            )
          })}
          {otherListings.map((listing) => (
            <FilledSlotCard
              key={listing.id}
              listing={listing}
              busy={busyKey === listing.id}
              onLinkUpdate={(url) =>
                void mutate(listing.id, () =>
                  api.updateCompetitorListing(listing.id, {
                    store: listing.store,
                    url,
                    is_active: true,
                  })
                )
              }
              onCheck={(url) =>
                void mutate(listing.id, async () => {
                  if (url !== listing.url.trim()) {
                    await api.updateCompetitorListing(listing.id, {
                      store: listing.store,
                      url,
                      is_active: true,
                    })
                  }
                  return api.checkCompetitorListing(listing.id)
                })
              }
              onDelete={() => void removeListing(listing.id)}
            />
          ))}
        </div>
      )}
    </section>
  )
}
