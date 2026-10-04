import { expect, test } from "@playwright/test"

// Backend-free: shell, form rendering, static KPIs, mobile drawer.
// Full login→products mutation flow needs a running API + seeded admin.

test("root redirects to dashboard with Persian RTL shell", async ({ page }) => {
  await page.goto("/")
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.locator("html")).toHaveAttribute("lang", "fa")
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl")
})

test("login page shows Persian admin form", async ({ page }) => {
  await page.goto("/login")
  await expect(page.getByRole("heading", { name: "ورود مدیر" })).toBeVisible()
  await expect(page.getByLabel("نام کاربری")).toBeVisible()
  await expect(page.getByLabel("گذرواژه")).toBeVisible()
  await expect(page.getByRole("button", { name: "ورود" })).toBeVisible()
})

test("dashboard shows Persian-formatted KPIs", async ({ page }) => {
  await page.goto("/dashboard")
  await expect(page.getByRole("heading", { name: "داشبورد" })).toBeVisible()
  await expect(page.getByText("۱٬۲۵۰٬۰۰۰", { exact: true })).toBeVisible()
  await expect(page.getByText("۴۸", { exact: true })).toBeVisible()
})

test("mobile opens navigation drawer from the right", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/dashboard")
  await page.getByRole("button", { name: "Toggle Sidebar" }).click()
  await expect(page.getByRole("link", { name: "محصولات" })).toBeVisible()
})
