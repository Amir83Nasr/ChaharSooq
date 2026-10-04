import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  transpilePackages: ["@workspace/ui"],
  // ponytail: تک IP محیط dev؛ برای بازه بزرگ‌تر ALLOWED_DEV_ORIGINS=a,b را ست کنید.
  allowedDevOrigins: process.env.ALLOWED_DEV_ORIGINS
    ? process.env.ALLOWED_DEV_ORIGINS.split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : ["192.168.1.20", "192.168.1.21"],
}

export default nextConfig
