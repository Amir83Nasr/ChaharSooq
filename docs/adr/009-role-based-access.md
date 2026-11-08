# ADR 009 — Role-based access (admin vs viewer)

Date: 2026-11-07 · Status: superseded by [ADR 010](010-owner-role.md)

> The viewer rules below still hold; the top-level role is now `owner` and
> `admin` is the middle management role. See ADR 010.

## Context

Every account had the same full-management access. The shop needs read-only
accounts (for people who only need to look at the catalog and prices) and a
way for an admin to create or remove those accounts without touching the
database.

## Decision

- Add `admins.role` with two values: `admin` (full management, including user
  management) and `viewer` (read-only). Existing rows migrate as `admin`.
- Two guards in `app/api/dependencies.py`:
  - `require_user` — any signed-in account, used by read endpoints.
  - `require_admin` — signed-in account with role `admin`, used by every write
    endpoint and by `/api/v1/users*`.
- `GET/POST /api/v1/users` and `DELETE /api/v1/users/{id}` are admin-only.
  Admins can create `admin` or `viewer` accounts and delete accounts.
- An admin cannot delete their own account, and the last admin cannot be
  removed. Deleting an account also deletes its active sessions.
- The frontend receives `role` from `/auth/me`. The sidebar hides the سیستم
  (settings/users) group from viewers, `/settings` and `/users` redirect
  viewers to `/products`, and write controls (sync buttons, competitor-link
  editing) are hidden. Backend guards remain the source of truth.

## Alternatives

- Separate `viewers` table: rejected — duplicates login/session handling and
  the username uniqueness rule.
- Permission matrix per resource: rejected — two roles cover the current need;
  a matrix can replace the `role` check later without changing the routes.

## Consequences

- Every new endpoint must choose `require_user` (read) or `require_admin`
  (write); using the old single guard is no longer possible.
- Viewers can read the catalog, dashboard, integration pages, and settings
  values needed by those views, but every mutation returns `403 forbidden`.
- User management is self-service through the panel; production no longer
  needs a database script to add a viewer.
