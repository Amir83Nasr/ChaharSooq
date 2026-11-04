// Fail-fast guard for Vercel production builds.
//
// The browser calls same-origin /api/* and Next rewrites to API_BASE. If a
// production deployment is built while API_URL_INTERNAL/NEXT_PUBLIC_API_URL
// still point at localhost, the deployed frontend silently proxies to itself.
// Catch that at build time instead of shipping a broken deployment.
//
// Runs before `next build` (see the `build` script in package.json). Passes
// everywhere except Vercel production builds with a loopback API origin.

const origin = (
  process.env.API_URL_INTERNAL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000"
).replace(/\/+$/, "")

const isLoopback =
  /^(https?:\/\/)?(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$/i.test(origin)

if (process.env.VERCEL_ENV === "production" && isLoopback) {
  console.error(
    `[check-vercel-env] refusing production build: API origin is loopback (${origin}).\n` +
      "Set API_URL_INTERNAL (and NEXT_PUBLIC_API_URL) to the FastAPI origin in the " +
      "Vercel dashboard → Project → Settings → Environment Variables (Production), " +
      "then redeploy."
  )
  process.exit(1)
}

console.log(`[check-vercel-env] ok (api origin: ${origin})`)
