"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ExternalLink,
  LoaderCircle,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
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

/** فروشگاه‌های قابل انتخاب در دیالوگ محصول (فقط لوازم خانگی). */
const DIALOG_STORES: CompetitorStore[] = ["digikala", "technolife"]

const STORE_LABELS: Record<CompetitorStore, string> = {
  digikala: "دیجی‌کالا",
  technolife: "تکنولایف",
  other: "سایر فروشگاه‌ها",
}

/** هر دو فروشگاه لینک دستی‌اند و نسبت به جست‌وجوی خودکار آینده بر اساس نام کالا اولویت دارند. */
const STORE_OPTION_LABELS: Record<CompetitorStore, string> = {
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

/** برای هر فروشگاه (دیجی‌کالا / تکنولایف) فقط یک لینک دستی مجاز است. */
const SINGLE_LINK_STORES: ReadonlySet<CompetitorStore> = new Set([
  "digikala",
  "technolife",
])

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

/**
 * دیجی‌کالا درخواست خودکار را تشخیص می‌دهد و صفحهٔ خالی برمی‌گرداند؛
 * پس بررسی لینک فقط برای تکنولایف فعال است.
 */
const AUTO_CHECK_STORES: ReadonlySet<CompetitorStore> = new Set(["technolife"])

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

function PriceListingCard({
  listing,
  busy,
  takenStores,
  onCheck,
  onSave,
  onToggle,
  onDelete,
}: {
  listing: CompetitorListing
  busy: boolean
  takenStores: ReadonlySet<CompetitorStore>
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
  const autoCheck = AUTO_CHECK_STORES.has(store)
  const trimmedUrl = url.trim()
  const urlMismatch =
    trimmedUrl !== "" && !isUrlMatchingStore(trimmedUrl, store)
  const storeTakenByOther =
    SINGLE_LINK_STORES.has(store) &&
    store !== listing.store &&
    takenStores.has(store)

  return (
    <article className="space-y-3 rounded-lg border border-border bg-background p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{listingStoreLabel(listing)}</Badge>
          <Badge variant={statusBadgeVariant(listing.status)}>
            {listing.is_active ? STATUS_LABELS[listing.status] : "غیرفعال"}
          </Badge>
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
          {listing.price_is_fresh && listing.effective_price !== null ? (
            <p className="text-base font-semibold">
              <Price
                value={Math.round(
                  listing.effective_currency === "IRR"
                    ? listing.effective_price / 10
                    : listing.effective_price
                )}
              />
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

      {store === "digikala" ? (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-700 dark:text-amber-300">
          بررسی خودکار دیجی‌کالا فعلاً در دسترس نیست؛ قیمت را دستی وارد و ذخیره
          کنید.
        </p>
      ) : null}

      {listing.last_error ? (
        <p role="alert" className="text-xs text-destructive">
          {listing.last_error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">
          لینک صفحهٔ محصول
        </p>
        <div className="space-y-2">
          <Select
            value={store}
            onValueChange={(value) => setStore(value as CompetitorStore)}
          >
            <SelectTrigger
              aria-label="فروشگاه یا سایت منبع"
              className="w-full sm:w-48"
            >
              <SelectValue>{STORE_OPTION_LABELS[store]}</SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              {DIALOG_STORES.map((option) => {
                const disabled =
                  SINGLE_LINK_STORES.has(option) &&
                  option !== listing.store &&
                  takenStores.has(option)
                return (
                  <SelectItem key={option} value={option} disabled={disabled}>
                    {STORE_OPTION_LABELS[option]}
                  </SelectItem>
                )
              })}
              {listing.store === "other" ? (
                <SelectItem value="other">سایر فروشگاه‌ها</SelectItem>
              ) : null}
            </SelectContent>
          </Select>
          <div className="min-w-0 space-y-1">
            <Input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              onBlur={(event) => setUrl(event.target.value.trim())}
              placeholder={STORE_URL_PLACEHOLDERS[store]}
              aria-label="لینک صفحه محصول"
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
            />
            {STORE_URL_HINTS[store] ? (
              <p className="text-[11px] leading-4 text-muted-foreground">
                {STORE_URL_HINTS[store]}
              </p>
            ) : null}
            {urlMismatch ? (
              <p
                role="alert"
                className="text-[11px] leading-4 text-destructive"
              >
                دامنهٔ لینک با فروشگاه انتخاب‌شده هم‌خوانی ندارد.
              </p>
            ) : null}
            {storeTakenByOther ? (
              <p
                role="alert"
                className="text-[11px] leading-4 text-destructive"
              >
                برای {STORE_LABELS[store]} قبلاً یک لینک ثبت شده است؛ ابتدا لینک
                قبلی را حذف کنید.
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">قیمت دستی</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_9rem]">
          <Input
            value={manualPrice === "" ? "" : formatPersianNumber(manualPrice)}
            onChange={(event) =>
              setManualPrice(parsePriceFilterInput(event.target.value))
            }
            placeholder="مثلاً ۲۵٬۰۰۰٬۰۰۰"
            aria-label="قیمت دستی"
            inputMode="numeric"
            className="col-span-2 sm:col-span-1"
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
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={busy || storeTakenByOther || trimmedUrl === ""}
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
        {autoCheck ? (
          <Button
            size="sm"
            variant="outline"
            disabled={busy || storeTakenByOther || trimmedUrl === ""}
            onClick={() => onCheck(store, url.trim())}
          >
            {busy ? <LoaderCircle className="animate-spin" /> : <RefreshCw />}
            بررسی لینک
          </Button>
        ) : null}
        <span className="ms-auto flex gap-1">
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
        </span>
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

  const takenStores = new Set(listings.map((listing) => listing.store))
  const trimmedNewUrl = url.trim()
  const newUrlMismatch =
    trimmedNewUrl !== "" && !isUrlMatchingStore(trimmedNewUrl, store)
  const newStoreTaken = SINGLE_LINK_STORES.has(store) && takenStores.has(store)

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
    const trimmed = url.trim()
    if (!trimmed) return
    if (SINGLE_LINK_STORES.has(store) && takenStores.has(store)) {
      setError(`برای ${STORE_LABELS[store]} قبلاً یک لینک ثبت شده است.`)
      return
    }
    setBusyId("create")
    try {
      const created = await api.createCompetitorListing(
        productId,
        store,
        trimmed
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
          لینک‌های دستی دیجی‌کالا و تکنولایف در اولویت‌اند و نسبت به جست‌وجوی
          خودکار آینده بر اساس نام کالا اولویت خواهند داشت. برای هر فروشگاه فقط
          یک لینک دستی می‌توان ثبت کرد. قیمت تکنولایف با «بررسی لینک» به‌صورت
          خودکار به‌روزرسانی می‌شود؛ قیمت دیجی‌کالا را دستی وارد کنید. قیمت فقط
          تا ۲۴ ساعت تازه محسوب می‌شود.
        </p>
      </div>

      <form onSubmit={addListing} className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">
          افزودن لینک دستی جدید
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Select
            value={store}
            onValueChange={(value) => setStore(value as CompetitorStore)}
          >
            <SelectTrigger aria-label="فروشگاه رقیب" className="w-full sm:w-48">
              <SelectValue>{STORE_OPTION_LABELS[store]}</SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              {DIALOG_STORES.map((option) => (
                <SelectItem
                  key={option}
                  value={option}
                  disabled={
                    SINGLE_LINK_STORES.has(option) && takenStores.has(option)
                  }
                >
                  {STORE_OPTION_LABELS[option]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="submit"
            disabled={busyId !== null || newStoreTaken || trimmedNewUrl === ""}
            className="w-full sm:ms-auto sm:w-auto"
          >
            {busyId === "create" ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Plus />
            )}
            افزودن لینک
          </Button>
        </div>
        <div className="min-w-0 space-y-1">
          <Input
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onBlur={(event) => setUrl(event.target.value.trim())}
            placeholder={STORE_URL_PLACEHOLDERS[store]}
            aria-label="لینک صفحهٔ محصول رقیب"
            aria-invalid={newUrlMismatch || undefined}
            title={trimmedNewUrl || undefined}
            dir="ltr"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            inputMode="url"
            className="h-10 w-full min-w-0 text-left text-sm text-ellipsis"
            required
          />
          {STORE_URL_HINTS[store] ? (
            <p className="text-[11px] leading-4 text-muted-foreground">
              {STORE_URL_HINTS[store]}
            </p>
          ) : null}
          {newUrlMismatch ? (
            <p role="alert" className="text-[11px] leading-4 text-destructive">
              دامنهٔ لینک با فروشگاه انتخاب‌شده هم‌خوانی ندارد.
            </p>
          ) : null}
          {newStoreTaken ? (
            <p role="alert" className="text-[11px] leading-4 text-destructive">
              برای {STORE_LABELS[store]} قبلاً یک لینک ثبت شده است؛ برای ثبت
              لینک جدید ابتدا لینک قبلی را حذف کنید.
            </p>
          ) : null}
        </div>
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
              takenStores={takenStores}
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
