import { redirect } from "next/navigation"

/** Pricing moved to its own top-level page; keep old bookmarks working. */
export default function LegacyPricingPage() {
  redirect("/pricing")
}
