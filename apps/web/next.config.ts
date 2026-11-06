import type { NextConfig } from "next"

import { loadSharedEnv } from "./scripts/load-env.mjs"

// ─── Shared env loading (dev / mobile) ──────────────────────────────────
// Next.js only reads .env* from the app directory (apps/web); the repo-root
// files are loaded via scripts/load-env.mjs (single place for LAN/mobile IP
// whitelisting) without overriding values already in the environment.
loadSharedEnv(process.cwd())

// Same-origin API proxy: browser talks only to the Next host (/api/*),
// Next rewrites to the FastAPI origin. Session cookie stays first-party,
// so no third-party-cookie / CORS friction in production.
const API_BASE = (
  process.env.API_URL_INTERNAL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000"
).replace(/\/+$/, "")

const nextConfig: NextConfig = {
  transpilePackages: ["@workspace/ui"],
  poweredByHeader: false,
  // LAN/mobile dev: set ALLOWED_DEV_ORIGINS=a,b (root or apps/web .env.local).
  // Empty by default, so only localhost may load the dev server.
  allowedDevOrigins: process.env.ALLOWED_DEV_ORIGINS
    ? process.env.ALLOWED_DEV_ORIGINS.split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : [],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          // Mirrors the API's frame policy so the panel can never be framed.
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none'",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ]
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE}/api/:path*` }]
  },
}

export default nextConfig
