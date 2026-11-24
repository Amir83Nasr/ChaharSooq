# ADR 032 — Standalone pricing page in the system sidebar

Date: 2026-11-24 · Status: accepted · Relocates the pricing UI previously nested
under settings

## Context

Pricing controls (`SuggestedPriceSettings`) lived at `/settings/pricing`, behind
both the main sidebar's تنظیمات entry and the in-settings navigation / overview
cards. Following the same reasoning as
[ADR 029](029-standalone-backup-page.md) for backup, the owner asked for pricing
to be a first-class entry in the main sidebar's "سیستم" group — directly below
تنظیمات and above پشتیبان‌گیری — so it gets its own space and finer control
instead of competing with the other settings sections. The backend settings API
(`/api/v1/settings`) is unrelated to the UI location and stays unchanged.

## Decision

- The page moves to the top-level route `/pricing` under the dashboard layout.
  It keeps the same full-management server guard as settings
  (`getSessionAdmin()` + `isAdmin()`); viewers are redirected as before.
- The sidebar shows قیمت‌گذاری between تنظیمات and پشتیبان‌گیری in the
  "سیستم" group, so it disappears for viewers along with the rest of the group.
- The pricing item is removed from the settings navigation and the settings
  overview; settings no longer owns pricing UI.
- `/settings/pricing` redirects to `/pricing` so existing bookmarks keep working.
- Pricing UI components stay under `apps/web/components/settings/`; the route
  move does not rename or reorganize them.

## Consequences

- The breadcrumb segment map keeps its existing `pricing` label because the
  route is now a single top-level segment.
- A new page metadata title (`چهارسوق | قیمت‌گذاری`) replaces the old
  settings-prefixed title.
- e2e unauthenticated-route coverage lists `/pricing` instead of the removed
  settings subpage.
- The settings API contract and per-product pricing modes from ADR 030/031 are
  unaffected.
