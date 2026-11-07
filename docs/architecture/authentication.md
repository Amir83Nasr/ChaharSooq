# Authentication — چهارسوق

Password flow: `POST /api/v1/auth/login` → HttpOnly session cookie → `GET /api/v1/auth/me` → dashboard; `POST /api/v1/auth/logout` clears.

- Passwords: Argon2id (`argon2-cffi`), never plaintext, never logged.
- Sessions: server-side rows (`admin_sessions`), opaque `secrets.token_urlsafe(48)` tokens, SHA-256 stored, TTL 12h default.
- Cookie: `HttpOnly`, `Secure` in production, `SameSite=Lax`, path `/`.
- Brute force: 10 login attempts / IP / minute → `429 rate_limited` (Persian message).
- Errors: non-sensitive Persian messages (`نام کاربری یا گذرواژه نادرست است`, `نیاز به ورود است`, `دسترسی ندارید`); validation → `validation_error` envelope.
- Frontend: no `localStorage` tokens; `credentials: "include"` fetch client; login form with labels, field errors, and `role="alert"`. `(dashboard)` routes are server-guarded via `lib/auth.ts` (`GET /api/v1/auth/me` with forwarded cookies, redirect to `/login` on failure); logout requires dialog confirmation before `POST /api/v1/auth/logout`.

## Roles

Every account has one role in `admins.role`:

| Role     | Can do                                                                                     |
| -------- | ------------------------------------------------------------------------------------------ |
| `admin`  | Everything: reads, catalog/settings writes, sync triggers, and user management.            |
| `viewer` | Read-only: catalog, dashboard, integration pages, and the settings values those views use. |

- Backend: read routes depend on `require_user`; every write route and `/api/v1/users*` depends on `require_admin`. A viewer calling a write endpoint gets `403 forbidden` (`دسترسی ندارید`).
- User management: an admin lists/creates/deletes accounts at `/api/v1/users`. Creating accepts `username`, `password`, and `role` (default `viewer`). Passwords are minimum 8 characters. Deleting revokes that account's active sessions; an admin cannot delete their own account, and the last admin cannot be removed.
- Frontend: `/auth/me` returns `id`, `username`, and `role`. The session context hides write controls and the settings/users navigation for viewers; `/settings` and `/users` redirect viewers to `/products`. These are UX guards only — the API enforces the role.

Seed: `scripts/seed_admin.py` creates an `admin`. New accounts are created in the panel at `/users`.

ADR: [002-authentication](../adr/002-authentication.md), [009-role-based-access](../adr/009-role-based-access.md).
