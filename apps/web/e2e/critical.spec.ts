import { expect, test } from "@playwright/test"

// Backend-free: auth redirects, the Persian login form, and the RTL shell.
// The full login→products mutation flow needs a running API + seeded admin.

test("unauthenticated routes land on the Persian RTL login page", async ({
  page,
}) => {
  for (const path of [
    "/",
    "/products",
    "/dashboard",
    "/settings",
    "/settings/pricing",
    "/settings/sync",
    "/settings/inventory",
    "/settings/appearance",
  ]) {
    await page.goto(path)
    await expect(page).toHaveURL(/\/login$/)
  }
  await expect(page.locator("html")).toHaveAttribute("lang", "fa")
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
})

test("login page shows the Persian admin form", async ({ page }) => {
  await page.goto("/login")
  await expect(
    page.getByRole("heading", { name: "ورود به چهارسوق" })
  ).toBeVisible()
  await expect(page.getByLabel("نام کاربری")).toBeVisible()
  await expect(page.getByLabel("گذرواژه")).toBeVisible()

  const submit = page.getByRole("button", { name: "ورود" })
  await expect(submit).toBeDisabled()
  await page.getByLabel("نام کاربری").fill("admin")
  await page.getByLabel("گذرواژه").fill("secret123")
  await expect(submit).toBeEnabled()
})

test("login form stays usable at mobile width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/login")
  await expect(
    page.getByRole("heading", { name: "ورود به چهارسوق" })
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "تغییر تم" })).toBeVisible()
})
