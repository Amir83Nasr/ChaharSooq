import { cache } from "react"
import { cookies } from "next/headers"

import { apiOrigin } from "./env"
import type { SessionUser } from "./session"

/* Server-side session check — forwards browser cookies to the API. */

const API = apiOrigin()

/**
 * One `/auth/me` call per request even when nested layouts both check the
 * session (React's per-request cache dedupes it).
 */
export const getSessionAdmin = cache(async (): Promise<SessionUser | null> => {
  const cookieHeader = (await cookies()).toString()
  let res: Response
  try {
    res = await fetch(`${API}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
      // Never hang a page render on a sick API — fail closed to login.
      signal: AbortSignal.timeout(5000),
    })
  } catch {
    // API unreachable from the web server → check API_URL_INTERNAL on the host.
    // Never log cookieHeader here (session secret material).
    console.error("getSessionAdmin: API unreachable", { host: API })
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
    role: data.role === "admin" ? "admin" : "viewer",
  }
})
