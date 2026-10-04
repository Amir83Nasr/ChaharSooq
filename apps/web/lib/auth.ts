import { cookies } from "next/headers"

/* Server-side session check — forwards browser cookies to the API. */

const API =
  process.env.API_URL_INTERNAL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000"

export interface SessionAdmin {
  username: string
}

export async function getSessionAdmin(): Promise<SessionAdmin | null> {
  const cookieHeader = (await cookies()).toString()
  try {
    const res = await fetch(`${API}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    })
    if (!res.ok) return null
    return (await res.json()) as SessionAdmin
  } catch {
    // API down → treat as unauthenticated (safe default: deny).
    return null
  }
}
