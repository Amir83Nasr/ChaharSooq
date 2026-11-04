// Temporary sidebar animation profiler (delete after use).
import { chromium } from "@playwright/test"

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000"

async function measureToggle(page, label) {
  const stats = await page.evaluate(async () => {
    const frames = []
    const longtasks = []
    const po = new PerformanceObserver((list) => {
      for (const e of list.getEntries()) longtasks.push(e.duration)
    })
    po.observe({ entryTypes: ["longtask"] })
    await new Promise((resolve) => {
      const start = performance.now()
      const tick = (t) => {
        frames.push(t)
        if (t - start < 1200) requestAnimationFrame(tick)
        else resolve()
      }
      requestAnimationFrame(tick)
    })
    // small wait so the longtask observer flushes
    await new Promise((r) => setTimeout(r, 300))
    po.disconnect()
    return { frames, longtasks }
  })
  const { frames, longtasks } = stats
  const gaps = []
  for (let i = 1; i < frames.length; i++) gaps.push(frames[i] - frames[i - 1])
  gaps.sort((a, b) => a - b)
  const over50 = gaps.filter((g) => g > 50).length
  const over100 = gaps.filter((g) => g > 100).length
  const p95 = gaps[Math.floor(gaps.length * 0.95)] ?? 0
  const max = gaps[gaps.length - 1] ?? 0
  const ltTotal = longtasks.reduce((a, b) => a + b, 0)
  console.log(
    `${label}: frames=${frames.length} p95=${p95.toFixed(1)}ms max=${max.toFixed(1)}ms >50ms=${over50} >100ms=${over100} longtasks=${longtasks.length} ltTotal=${ltTotal.toFixed(0)}ms`
  )
  return { gaps, longtasks }
}

const browser = await chromium.launch()

// Login via API (bypasses the dev-server HMR input quirk), then inject session.
const loginRes = await fetch(`${BASE}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: "admin", password: "secret123" }),
})
if (!loginRes.ok) throw new Error(`login failed: ${loginRes.status}`)
const setCookie = loginRes.headers.get("set-cookie") ?? ""
const session = /charsooq_session=([^;]+)/.exec(setCookie)?.[1]
if (!session) throw new Error("no session cookie")
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
})
await context.addCookies([
  { name: "charsooq_session", value: session, domain: "127.0.0.1", path: "/" },
])
const page = await context.newPage()
await page.goto(`${BASE}/products`)
await page.waitForTimeout(1500)
console.log("logged in:", page.url())

for (const path of ["/dashboard", "/products"]) {
  await page.goto(`${BASE}${path}`)
  await page.waitForTimeout(1500)
  const trigger = page.locator('[data-sidebar="trigger"]').first()
  await trigger.waitFor({ timeout: 10000 })
  // CDP layout metrics around one toggle
  const cdp = await page.context().newCDPSession(page)
  await cdp.send("Performance.enable")
  const before = await cdp.send("Performance.getMetrics")
  const m0 = Object.fromEntries(before.metrics.map((m) => [m.name, m.value]))
  await trigger.click()
  await measureToggle(page, `${path} close`)
  const after = await cdp.send("Performance.getMetrics")
  const m1 = Object.fromEntries(after.metrics.map((m) => [m.name, m.value]))
  console.log(
    `  layoutΔ=${((m1.LayoutDuration ?? 0) - (m0.LayoutDuration ?? 0)).toFixed(3)}s recalcΔ=${((m1.RecalcStyleDuration ?? 0) - (m0.RecalcStyleDuration ?? 0)).toFixed(3)}s scriptΔ=${((m1.ScriptDuration ?? 0) - (m0.ScriptDuration ?? 0)).toFixed(3)}s`
  )
  await page.waitForTimeout(800)
  await trigger.click()
  await measureToggle(page, `${path} open`)
  await page.waitForTimeout(800)
}

// Screenshots mid-animation for visual inspection (collapse)
await page.goto(`${BASE}/dashboard`)
await page.waitForTimeout(1200)
const trigger = page.locator('[data-sidebar="trigger"]').first()
await trigger.click()
for (const [i, t] of [0, 100, 200, 300].entries()) {
  if (i > 0) await page.waitForTimeout(100)
  await page
    .locator('[data-slot="sidebar-wrapper"]')
    .screenshot({ path: `/tmp/sb-collapse-${t}ms.png` })
}
await page.waitForTimeout(600)
await page
  .locator('[data-slot="sidebar-wrapper"]')
  .screenshot({ path: `/tmp/sb-collapsed.png` })

await browser.close()
console.log("done")
