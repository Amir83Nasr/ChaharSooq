import { cache } from "react"
import { cookies } from "next/headers"

import { apiOrigin } from "./env"
import type { SessionUser } from "./session"

/* Server-side session check — forwards browser cookies to the API. */

const API = apiOrigin()
// Keep in sync with the API's SESSION_COOKIE_NAME; an anonymous visitor is
// already known to be signed out, so there is no reason to call /auth/me.
const SESSION_COOKIE = (
  process.env.SESSION_COOKIE_NAME ?? "charsooq_session"
).trim()

function hasSessionCookie(header: string): boolean {
  return header
    .split(";")
    .some((part) => part.trimStart().startsWith(`${SESSION_COOKIE}=`))
}

/**
 * One `/auth/me` call per request even when nested layouts both check the
 * session (React's per-request cache dedupes it).
 */
export const getSessionAdmin = cache(async (): Promise<SessionUser | null> => {
  const cookieHeader = (await cookies()).toString()
  if (!hasSessionCookie(cookieHeader)) return null

  let res: Response
  try {
    res = await fetch(`${API}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
      // Never hang a page render on a sick API — fail closed to login.
      signal: AbortSignal.timeout(5000),
    })
  } catch (error) {
    // API unreachable from the web server → check API_URL_INTERNAL on the host.
    // Never log cookieHeader here (session secret material); the fetch error
    // only carries the transport cause (e.g. ECONNREFUSED / timeout).
    const cause = error instanceof Error ? error.message : String(error)
    // The page degrades safely to the login screen, so this is a warning, not
    // a fatal render error — but it stays visible for local diagnosis.
    console.warn("getSessionAdmin: API unreachable", { host: API, cause })
    return null
  }
  if (!res.ok) {
    if (res.status !== 401)
      console.error("getSessionAdmin: unexpected status", {
        host: API,
        status: res.status,
      })
    return null
  }
  const data = (await res.json()) as {
    id: number
    username: string
    role?: string
  }
  // Unknown/missing roles fail closed to the read-only level.
  return {
    id: data.id,
    username: data.username,
    role:
      data.role === "owner"
        ? "owner"
        : data.role === "admin"
          ? "admin"
          : "viewer",
  }
})
