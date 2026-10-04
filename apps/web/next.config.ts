import type { NextConfig } from "next"

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
  // ponytail: تک IP محیط dev؛ برای بازه بزرگ‌تر ALLOWED_DEV_ORIGINS=a,b را ست کنید.
  allowedDevOrigins: process.env.ALLOWED_DEV_ORIGINS
    ? process.env.ALLOWED_DEV_ORIGINS.split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : ["192.168.1.20", "192.168.1.21"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE}/api/:path*` }]
  },
}

export default nextConfig
