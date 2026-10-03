# Frontend — چهارسوق

- Next.js App Router, `lang="fa" dir="rtl"` in `apps/web/app/layout.tsx`.
- IRANYekanX via `next/font/local` (`apps/web/app/fonts.ts`, files in `apps/web/fonts/iran-yekan-x/`), weights 300–800.
- shadcn/ui primitives live in `packages/ui/src/components/`; sidebar uses the shadcn Sidebar block (`apps/web/components/app-sidebar.tsx`), cookie-persisted, icon-collapsible, mobile sheet.
- Shared Persian layer: `packages/ui/src/lib/{locale,number,currency,date,jalali}.ts` + `Price`, `PersianNumber`, `PersianDate/Time` components. No ad-hoc digit conversion.
- Routes: `/` → `/dashboard`; `(auth)/login` (client form + `lib/api.ts` typed client); `(dashboard)/{dashboard,products,reports,settings}` behind the sidebar layout with loading/empty/error states.
- Reusable UI: `PageHeader`, `EmptyState`/`ErrorState`, `Skeleton`, shadcn table/dialog/sheet/select/tabs/tooltip/sonner as needed.
