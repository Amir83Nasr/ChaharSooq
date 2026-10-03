# Authentication — چهارسوق

Admin password flow: `POST /api/v1/auth/login` → HttpOnly session cookie → `GET /api/v1/auth/me` → dashboard; `POST /api/v1/auth/logout` clears.

- Passwords: Argon2id (`argon2-cffi`), never plaintext, never logged.
- Sessions: server-side rows (`admin_sessions`), opaque `secrets.token_urlsafe(48)` tokens, SHA-256 stored, TTL 12h default.
- Cookie: `HttpOnly`, `Secure` in production, `SameSite=Lax`, path `/`.
- Brute force: 10 login attempts / IP / minute → `429 rate_limited` (Persian message).
- Errors: non-sensitive Persian messages (`نام کاربری یا گذرواژه نادرست است`, `نیاز به ورود است`); validation → `validation_error` envelope.
- Frontend: no `localStorage` tokens; `credentials: "include"` fetch client; login form with labels, field errors, and `role="alert"`.

ADR: [002-authentication](../adr/002-authentication.md).
