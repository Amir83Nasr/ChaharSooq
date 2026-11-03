/* Central server-side env access for the web app.
   Browser code must never import this module — it reads server-only
   variables (API_URL_INTERNAL). Client components use same-origin /api/*
   through the Next rewrite instead. */

function stripTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "")
}

/** FastAPI origin for server-to-server calls (rewrite target + lib/auth). */
export function apiOrigin(): string {
  return stripTrailingSlashes(
    process.env.API_URL_INTERNAL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://localhost:8000"
  )
}

/** Comma-separated LAN origins allowed to load the dev server. */
export function allowedDevOrigins(): string[] {
  return (process.env.ALLOWED_DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
}
