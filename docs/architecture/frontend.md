# Frontend — چهارسوق

- Next.js App Router, `lang="fa" dir="rtl"` in `apps/web/app/layout.tsx`.
- IRANYekanX via `next/font/local` (`apps/web/app/fonts.ts`, files in `apps/web/fonts/iran-yekan-x/`), weights 300–800.
- shadcn/ui primitives live in `packages/ui/src/components/`; sidebar uses the shadcn Sidebar block (`apps/web/components/app-sidebar.tsx`), cookie-persisted, icon-collapsible, mobile sheet.
- Shared Persian layer: `packages/ui/src/lib/{locale,number,currency,date,jalali}.ts` + `Price`, `PersianNumber`, `PersianDate/Time` components. No ad-hoc digit conversion.
- Routes: `/` → `/dashboard`; `(auth)/login` (client form + `lib/api.ts` typed client; logged-in users redirect to `/dashboard`); `(dashboard)/{dashboard,products,reports,settings}` behind a server-side session guard (`lib/auth.ts` → `GET /api/v1/auth/me`, redirect to `/login` when unauthenticated) with loading/empty/error states. Global `loading.tsx`/`error.tsx`/`not-found.tsx` at `app/`.
- Products route owns data-fetching in `page.tsx` (~300 lines); presentational pieces live in `(dashboard)/products/_components/{products-toolbar,products-table,product-dialogs}.tsx`. Generic `StatBadge`/`StockCell` stay in `components/products-*.tsx` for reuse. Sidebar lists only shipped routes (dashboard/products/settings).
- Logout: sidebar `خروج` opens a shadcn `Dialog` confirmation; confirm calls `POST /api/v1/auth/logout` then routes to `/login`.
- Reusable UI: `PageHeader`, `EmptyState`/`ErrorState`, `Skeleton`, shadcn table/dialog/sheet/select/tabs/tooltip/sonner as needed.
