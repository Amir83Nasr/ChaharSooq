"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ExternalLink,
  LoaderCircle,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Price } from "@workspace/ui/components/price"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  formatPersianNumber,
  parsePriceFilterInput,
} from "@workspace/ui/lib/number"
import { PersianDateTime } from "@workspace/ui/components/persian-date"
import {
  ApiRequestError,
  api,
  type CompetitorCurrency,
  type CompetitorListing,
  type CompetitorStore,
} from "@/lib/api"

const STORE_LABELS: Record<CompetitorStore, string> = {
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
  other: "سایر فروشگاه‌ها",
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

function toPersianError(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message
  return "عملیات انجام نشد. دوباره تلاش کنید."
}

function PriceListingCard({
  listing,
  busy,
  onCheck,
  onSave,
  onToggle,
  onDelete,
}: {
  listing: CompetitorListing
  busy: boolean
  onCheck: (store: CompetitorStore, url: string) => void
  onSave: (
    store: CompetitorStore,
    url: string,
    price: number | null,
    currency: CompetitorCurrency,
    inStock: boolean | null
  ) => void
  onToggle: () => void
  onDelete: () => void
}) {
  const [store, setStore] = useState<CompetitorStore>(listing.store)
  const [url, setUrl] = useState(listing.url)
  const [manualPrice, setManualPrice] = useState(
    listing.manual_price === null ? "" : String(listing.manual_price)
  )
  const [currency, setCurrency] = useState<CompetitorCurrency>(
    listing.manual_currency ?? listing.fetched_currency ?? "IRT"
  )
  const [inStock, setInStock] = useState(
    listing.manual_in_stock === null
      ? "unknown"
      : listing.manual_in_stock
        ? "yes"
        : "no"
  )

  useEffect(() => {
    setStore(listing.store)
    setUrl(listing.url)
    setManualPrice(
      listing.manual_price === null ? "" : String(listing.manual_price)
    )
    setCurrency(listing.manual_currency ?? listing.fetched_currency ?? "IRT")
    setInStock(
      listing.manual_in_stock === null
        ? "unknown"
        : listing.manual_in_stock
          ? "yes"
          : "no"
    )
  }, [listing])

  const numericPrice = parsePriceFilterInput(manualPrice)

  return (
    <article className="space-y-3 rounded-md border border-border bg-background p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <a
            href={listing.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full items-center gap-1 text-sm font-semibold text-primary hover:underline"
          >
            <span className="truncate">{listingStoreLabel(listing)}</span>
            <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
          </a>
          <p className="text-xs text-muted-foreground">
            وضعیت:{" "}
            {listing.is_active ? STATUS_LABELS[listing.status] : "غیرفعال"}
            {listing.last_checked_at ? (
              <>
                {" "}
                · آخرین بررسی{" "}
                <PersianDateTime value={listing.last_checked_at} />
              </>
            ) : (
              " · هنوز بررسی نشده"
            )}
          </p>
          {listing.last_error ? (
            <p role="alert" className="text-xs text-destructive">
              {listing.last_error}
            </p>
          ) : null}
        </div>
        <div className="text-start">
          {listing.price_is_fresh && listing.effective_price !== null ? (
            <p className="font-semibold">
              <Price
                value={Math.round(
                  listing.effective_currency === "IRR"
                    ? listing.effective_price / 10
                    : listing.effective_price
                )}
              />
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              قیمت تازه دریافت نشده
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {listing.effective_in_stock === null
              ? "موجودی نامشخص"
              : listing.effective_in_stock
                ? "موجود"
                : "ناموجود"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[10rem_minmax(0,1fr)]">
        <Select
          value={store}
          onValueChange={(value) => setStore(value as CompetitorStore)}
        >
          <SelectTrigger aria-label="فروشگاه یا سایت منبع">
            <SelectValue>{STORE_LABELS[store]}</SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="digikala">دیجی‌کالا</SelectItem>
            <SelectItem value="technolife">تکنولایف</SelectItem>
            <SelectItem value="other">سایر فروشگاه‌ها</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          aria-label="لینک صفحه محصول"
          dir="ltr"
          required
        />
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_9rem]">
        <Input
          value={manualPrice === "" ? "" : formatPersianNumber(manualPrice)}
          onChange={(event) =>
            setManualPrice(parsePriceFilterInput(event.target.value))
          }
          placeholder="قیمت دستی (اختیاری)"
          aria-label="قیمت دستی"
          inputMode="numeric"
        />
        <Select
          value={currency}
          onValueChange={(value) => setCurrency(value as CompetitorCurrency)}
        >
          <SelectTrigger aria-label="واحد پول">
            <SelectValue>{currency === "IRR" ? "ریال" : "تومان"}</SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="IRT">تومان</SelectItem>
            <SelectItem value="IRR">ریال</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={inStock}
          onValueChange={(value) => setInStock(value ?? "unknown")}
        >
          <SelectTrigger aria-label="موجودی فروشگاه">
            <SelectValue>
              {inStock === "yes"
                ? "موجود"
                : inStock === "no"
                  ? "ناموجود"
                  : "موجودی نامشخص"}
            </SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="unknown">موجودی نامشخص</SelectItem>
            <SelectItem value="yes">موجود</SelectItem>
            <SelectItem value="no">ناموجود</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => onCheck(store, url.trim())}
        >
          {busy ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}
          بررسی لینک
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() =>
            onSave(
              store,
              url.trim(),
              numericPrice === "" ? null : Number(numericPrice),
              currency,
              inStock === "unknown" ? null : inStock === "yes"
            )
          }
        >
          ذخیرهٔ اصلاحات
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={onToggle}>
          {listing.is_active ? "غیرفعال‌کردن" : "فعال‌کردن"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-destructive"
          disabled={busy}
          onClick={onDelete}
        >
          <Trash2 /> حذف
        </Button>
      </div>
    </article>
  )
}

export function ProductCompetitorPrices({ productId }: { productId: number }) {
  const [listings, setListings] = useState<CompetitorListing[]>([])
  const [store, setStore] = useState<CompetitorStore>("digikala")
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | "create" | null>(null)
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
    setBusyId(id)
    try {
      const updated = await action()
      setListings((current) =>
        current.map((listing) => (listing.id === id ? updated : listing))
      )
      setError(null)
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setBusyId(null)
    }
  }

  async function addListing(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!url.trim()) return
    setBusyId("create")
    try {
      const created = await api.createCompetitorListing(
        productId,
        store,
        url.trim()
      )
      setListings((current) => [...current, created])
      setUrl("")
      setError(null)
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setBusyId(null)
    }
  }

  async function removeListing(id: number) {
    setBusyId(id)
    try {
      await api.deleteCompetitorListing(id)
      setListings((current) => current.filter((listing) => listing.id !== id))
      setError(null)
    } catch (err) {
      setError(toPersianError(err))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="space-y-4 rounded-lg border border-border bg-muted/30 p-4 text-start">
      <div>
        <h3 className="font-semibold">قیمت فروشگاه‌های دیگر</h3>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          این بخش در فاز فعلی برای لوازم خانگی است. قیمت فقط تا ۲۴ ساعت تازه
          محسوب می‌شود؛ بررسی خودکار فقط برای دیجی‌کالا و تکنولایف انجام می‌شود.
          لینک سایر سایت‌ها فقط برای ثبت دستی ذخیره می‌شود.
        </p>
      </div>

      <form
        onSubmit={addListing}
        className="grid grid-cols-1 gap-2 sm:grid-cols-[10rem_minmax(0,1fr)_auto]"
      >
        <Select
          value={store}
          onValueChange={(value) => setStore(value as CompetitorStore)}
        >
          <SelectTrigger aria-label="فروشگاه رقیب">
            <SelectValue>{STORE_LABELS[store]}</SelectValue>
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="digikala">دیجی‌کالا</SelectItem>
            <SelectItem value="technolife">تکنولایف</SelectItem>
            <SelectItem value="other">سایر فروشگاه‌ها (ثبت دستی)</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="لینک صفحهٔ محصول"
          aria-label="لینک صفحهٔ محصول رقیب"
          dir="ltr"
          required
        />
        <Button type="submit" disabled={busyId !== null}>
          {busyId === "create" ? (
            <LoaderCircle className="animate-spin" />
          ) : (
            <Plus />
          )}
          افزودن لینک
        </Button>
      </form>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p className="text-sm text-muted-foreground">
          در حال بارگذاری منابع قیمت…
        </p>
      ) : listings.length ? (
        <div className="space-y-3">
          {listings.map((listing) => (
            <PriceListingCard
              key={listing.id}
              listing={listing}
              busy={busyId === listing.id}
              onCheck={(updatedStore, updatedUrl) =>
                void mutate(listing.id, async () => {
                  await api.updateCompetitorListing(listing.id, {
                    store: updatedStore,
                    url: updatedUrl,
                  })
                  return api.checkCompetitorListing(listing.id)
                })
              }
              onSave={(updatedStore, updatedUrl, price, currency, inStock) =>
                void mutate(listing.id, () =>
                  api.updateCompetitorListing(listing.id, {
                    store: updatedStore,
                    url: updatedUrl,
                    manual_price: price,
                    manual_currency: currency,
                    manual_in_stock: inStock,
                  })
                )
              }
              onToggle={() =>
                void mutate(listing.id, () =>
                  api.updateCompetitorListing(listing.id, {
                    is_active: !listing.is_active,
                  })
                )
              }
              onDelete={() => void removeListing(listing.id)}
            />
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
          هنوز لینک رقیبی برای این کالا ثبت نشده است.
        </p>
      )}
    </section>
  )
}
