// Shared dotenv loader for the web app (dev / LAN-mobile).
//
// Next.js only reads .env* from the app directory (apps/web). A single root
// .env.local is convenient for LAN/mobile dev (one place to whitelist IPs),
// so the repo-root env files are loaded here too — without overriding values
// already present in the process environment.
//
// Used by next.config.ts at build/dev time. Runtime code (lib/env.ts) reads
// the already-loaded process.env and must never import this module.

import fs from "node:fs"
import path from "node:path"

export function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return
  const content = fs.readFileSync(filePath, "utf8")
  for (const rawLine of content.split(/\r?\n/)) {
    let line = rawLine.trim()
    if (!line || line.startsWith("#")) continue
    // Support `export KEY=value` like dotenv does.
    if (line.startsWith("export ")) line = line.slice("export ".length).trim()
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

export function loadSharedEnv(appDir) {
  const repoRoot = path.resolve(appDir, "../..")
  loadEnvFile(path.join(repoRoot, ".env.local"))
  loadEnvFile(path.join(repoRoot, ".env"))
  loadEnvFile(path.join(appDir, ".env.local"))
  loadEnvFile(path.join(appDir, ".env"))
}
