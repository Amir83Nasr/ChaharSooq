# Authentication — چهارسوق

Password flow: `POST /api/v1/auth/login` → HttpOnly session cookie → `GET /api/v1/auth/me` → dashboard; `POST /api/v1/auth/logout` clears.

- Passwords: Argon2id (`argon2-cffi`), never plaintext, never logged.
- Sessions: server-side rows (`admin_sessions`), opaque `secrets.token_urlsafe(48)` tokens, SHA-256 stored, TTL 12h default.
- Cookie: `HttpOnly`, `Secure` in production mode (Staging and Production), `SameSite=Lax`, path `/`.
- Brute force: 10 login attempts / IP / minute → `429 rate_limited` (Persian message).
- Errors: non-sensitive Persian messages (`نام کاربری یا گذرواژه نادرست است`, `نیاز به ورود است`, `دسترسی ندارید`); validation → `validation_error` envelope.
- Frontend: no `localStorage` tokens; `credentials: "include"` fetch client; login form with labels, field errors, and `role="alert"`. `(dashboard)` routes are server-guarded via `lib/auth.ts` (`GET /api/v1/auth/me` with forwarded cookies, redirect to `/login` on failure); logout requires dialog confirmation before `POST /api/v1/auth/logout`.

## Roles

Every account has one role in `admins.role`:

| Role     | Can do                                                                                             |
| -------- | -------------------------------------------------------------------------------------------------- |
| `owner`  | Everything, including creating/removing admins. Comes only from `OWNER_USERNAME`/`OWNER_PASSWORD`. |
| `admin`  | Shop data (products, categories, settings, sync) and viewer management. Never sees other admins.   |
| `viewer` | Read-only: catalog, dashboard, integration pages, and the settings values those views use.         |

- The owner is env-managed: on every API boot (after migrations) `app/services/owner.py` creates the account if missing, re-hashes it when `OWNER_PASSWORD` changes, revokes its sessions, and demotes any other `owner` row. Production refuses to boot when the password is missing or shorter than 8 characters.
- Backend: read routes depend on `require_user`; every write route, `/api/v1/users*`, and `/api/v1/settings*` depend on `require_admin`, which accepts `owner` and `admin`. Owner-only decisions are made in `UserService` from the actor's role. A viewer calling a write endpoint gets `403 forbidden` (`دسترسی ندارید`).
- User management: `GET /api/v1/users` returns every account for the owner; an admin gets viewer accounts plus their own account (so the panel can mark the signed-in row). `POST` accepts `username`, `password`, and `role` (default `viewer`); an admin may create viewers only, the owner may also create admins. Passwords are minimum 8 characters. Deleting revokes that account's active sessions; nobody can delete their own account, the owner cannot be deleted from the panel, and the last remaining management account (owner or admin) cannot be removed. Because the owner cannot be deleted, the owner may remove every admin.
- Frontend: `/auth/me` returns `id`, `username`, and `role`. The session context treats `owner` and `admin` as management roles, hiding write controls and the settings/users navigation from viewers; `/settings` and `/users` redirect viewers to `/products`. An admin's `/users` form only offers the viewer role. These are UX guards only — the API enforces the role.

Seed: `scripts/seed_admin.py` ensures the env owner (same service as API boot). New admin/viewer accounts are created in the panel at `/users`.

ADR: [002-authentication](../adr/002-authentication.md), [009-role-based-access](../adr/009-role-based-access.md), [010-owner-role](../adr/010-owner-role.md).
