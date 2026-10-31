import type { NextConfig } from "next"
import fs from "node:fs"
import path from "node:path"

// ─── Shared env loading (dev / mobile) ──────────────────────────────────
// Next.js only reads .env* from the app directory (apps/web). A single root
// .env.local is convenient for LAN/mobile dev (one place to whitelist IPs),
// so we also load the repository-root env files here, without overriding
// values already present in the process environment.
function loadEnvFile(filePath: string) {
  if (!fs.existsSync(filePath)) return
  const content = fs.readFileSync(filePath, "utf8")
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith("#")) continue
    const eq = line.indexOf("=")
    if (eq === -1) continue
    const key = line.slice(0, eq).trim()
    if (!key || process.env[key] !== undefined) continue
    let value = line.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    process.env[key] = value
  }
}

const _appDir = process.cwd()
const _repoRoot = path.resolve(_appDir, "../..")
loadEnvFile(path.join(_repoRoot, ".env.local"))
loadEnvFile(path.join(_repoRoot, ".env"))
loadEnvFile(path.join(_appDir, ".env.local"))
loadEnvFile(path.join(_appDir, ".env"))

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
  // LAN/mobile dev: set ALLOWED_DEV_ORIGINS=a,b (root or apps/web .env.local).
  // Empty by default, so only localhost may load the dev server.
  allowedDevOrigins: process.env.ALLOWED_DEV_ORIGINS
    ? process.env.ALLOWED_DEV_ORIGINS.split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : [],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE}/api/:path*` }]
  },
}

export default nextConfig
