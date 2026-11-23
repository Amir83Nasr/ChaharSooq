import { redirect } from "next/navigation"

/** Backup moved to its own top-level page; keep old bookmarks working. */
export default function LegacyBackupPage() {
  redirect("/backup")
}
