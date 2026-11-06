import type { Metadata } from "next"

import {
  Clock,
  Columns3,
  MoonStar,
  PackageMinus,
  Rows3,
  Sigma,
  Store,
} from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"
import { PageHeader } from "@workspace/ui/layout/page-header"

import { InventoryThresholdSettings } from "@/components/settings/inventory-threshold-settings"
import { CompetitorStoreSettings } from "@/components/settings/competitor-store-settings"
import { CompetitorSyncIntervalSettings } from "@/components/settings/competitor-sync-interval-settings"
import { PageSizeSettings } from "@/components/settings/page-size-settings"
import { SyncIntervalSettings } from "@/components/settings/sync-interval-settings"
import { SuggestedPriceSettings } from "@/components/settings/suggested-price-settings"
import { TableColumnsSettings } from "@/components/settings/table-columns-settings"
import { ThemeSettings } from "@/components/settings/theme-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات" }

export default function SettingsPage() {
  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      <PageHeader title="تنظیمات" subtitle="پیکربندی فروشگاه" />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sigma className="size-4" />
            قیمت پیشنهادی
          </CardTitle>
          <CardDescription>
            وزن سهم قیمت رقیب برای هر دسته‌بندی (۰ تا ۱) با پیش‌نمایش زنده
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SuggestedPriceSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MoonStar className="size-4" />
            تم نمایش
          </CardTitle>
          <CardDescription>روشن، تیره یا همگام با سیستم‌عامل</CardDescription>
        </CardHeader>
        <CardContent>
          <ThemeSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Store className="size-4" />
            بازار پیش‌فرض قیمت رقبا
          </CardTitle>
          <CardDescription>
            در جدول محصولات، ستون «قیمت رقبا» اول قیمت کدام فروشگاه را نشان
            بدهد؛ تغییر بازار در هدر جدول موقتی است
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CompetitorStoreSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rows3 className="size-4" />
            تعداد ردیف پیش‌فرض جدول
          </CardTitle>
          <CardDescription>
            چند ردیف در هر صفحه جدول محصولات نمایش داده شود؛ «همه» کل لیست را
            بدون صفحه‌بندی نمایش می‌دهد
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PageSizeSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Columns3 className="size-4" />
            ستون‌های جدول محصولات
          </CardTitle>
          <CardDescription>
            ستون‌هایی که در جدول محصولات (نمای دسکتاپ) نمایش داده می‌شوند را
            انتخاب کنید؛ پنهان‌کردن ستون‌های کم‌کاربرد فضای بیشتری برای بقیه
            ستون‌ها باز می‌کند
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TableColumnsSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PackageMinus className="size-4" />
            آستانه موجودی کم
          </CardTitle>
          <CardDescription>
            از چه موجودی به پایین، کالا «کم» محسوب شود
          </CardDescription>
        </CardHeader>
        <CardContent>
          <InventoryThresholdSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="size-4" />
            فاصله به‌روزرسانی خودکار قیمت رقبا
          </CardTitle>
          <CardDescription>
            هر چند ساعت یکبار قیمت همه فروشگاه‌های دیگر به‌طور خودکار به‌روز
            شود؛ فاصله کمتر فشار بیشتر روی فروشگاه‌ها می‌آورد
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CompetitorSyncIntervalSettings />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="size-4" />
            فاصله به‌روزرسانی خودکار
          </CardTitle>
          <CardDescription>
            هر چند ساعت یکبار کاتالوگ محصولات از حسابداری به‌روز شود
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SyncIntervalSettings />
        </CardContent>
      </Card>
    </div>
  )
}
