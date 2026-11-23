# ADR 029 — Standalone backup page in the system sidebar

Date: 2026-11-23 · Status: accepted · Relocates the owner-facing page described
in [ADR 022](022-owner-configured-backup-orchestration.md)

## Context

The owner backup controls originally lived at `/settings/backup`, reachable
through the in-settings navigation and the settings overview card. Owners asked
for backup management to sit alongside users as a first-class entry in the main
sidebar's "سیستم" group, directly below تنظیمات, rather than being nested inside
settings. The backend API path `/api/v1/settings/backup` is unrelated to the UI
location and stays unchanged.

## Decision

- The page moves to the top-level route `/backup` under the dashboard layout.
  It keeps the owner-only server guard (`getSessionAdmin()` + `isOwner()`); a
  non-owner is redirected as before.
- The sidebar shows پشتیبان\u200cگیری between تنظیمات and کاربران in the "سیستم"
  group, visible only to the owner. Viewers still never see the group, and
  non-owner management accounts do not see the backup entry.
- The backup item is removed from the settings navigation and the settings
  overview; settings no longer owns backup UI.
- `/settings/backup` redirects to `/backup` so existing bookmarks keep working.
- Backup UI components stay under `apps/web/components/settings/`; the route
  move does not rename or reorganize them.

## Consequences

- The breadcrumb segment map keeps its existing `backup` label because the route
  is now a single top-level segment.
- A new page metadata title (`چهارسوق | پشتیبان\u200cگیری`) replaces the old
  settings-prefixed title.
- e2e unauthenticated-route coverage lists `/backup` instead of the removed
  settings subpage.
- The API contract and backup metadata workflow from ADR 022/023 are unaffected.
