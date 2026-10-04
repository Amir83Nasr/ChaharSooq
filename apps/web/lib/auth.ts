import { cookies } from "next/headers"

/* Server-side session check — forwards browser cookies to the API. */

const API = (
  process.env.API_URL_INTERNAL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000"
).replace(/\/+$/, "")

export interface SessionAdmin {
  username: string
}

export async function getSessionAdmin(): Promise<SessionAdmin | null> {
  const cookieHeader = (await cookies()).toString()
  let res: Response
  try {
    res = await fetch(`${API}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    })
  } catch {
    // API unreachable from the web server → check API_URL_INTERNAL on the host.
    // Never log cookieHeader here (session secret material).
    console.error("getSessionAdmin: API unreachable", { host: API })
    return null
  }
  if (!res.ok) {
    if (res.status !== 401) console.error("getSessionAdmin: unexpected status", { host: API, status: res.status })
    return null
  }
  return (await res.json()) as SessionAdmin
}
