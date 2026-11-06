import type { Metadata } from "next"
import { Columns3, MoonStar, Rows3 } from "lucide-react"

import { PageSizeSettings } from "@/components/settings/page-size-settings"
import { SettingsSection } from "@/components/settings/settings-section"
import { TableColumnsSettings } from "@/components/settings/table-columns-settings"
import { ThemeSettings } from "@/components/settings/theme-settings"

export const metadata: Metadata = { title: "چهارسوق | تنظیمات — نمایش" }

export default function AppearanceSettingsPage() {
  return (
    <>
      <SettingsSection
        icon={MoonStar}
        title="تم نمایش"
        description="روشن، تیره یا همگام با سیستم‌عامل"
      >
        <ThemeSettings />
      </SettingsSection>
      <SettingsSection
        icon={Rows3}
        title="تعداد ردیف پیش‌فرض جدول"
        description="چند ردیف در هر صفحه جدول محصولات نمایش داده شود؛ «همه» کل لیست را بدون صفحه‌بندی نمایش می‌دهد"
      >
        <PageSizeSettings />
      </SettingsSection>
      <SettingsSection
        icon={Columns3}
        title="ستون‌های جدول محصولات"
        description="ستون‌هایی که در جدول محصولات (نمای دسکتاپ) نمایش داده می‌شوند را انتخاب کنید؛ پنهان‌کردن ستون‌های کم‌کاربرد فضای بیشتری برای بقیه ستون‌ها باز می‌کند"
      >
        <TableColumnsSettings />
      </SettingsSection>
    </>
  )
}
