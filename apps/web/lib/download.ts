/* CSV download helper — keeps session cookies and API error messages intact.

   The typed JSON client (`api.ts`) always sets `Content-Type: application/json`
   and parses a body, so downloads go through this small dedicated path. */

import { ApiRequestError } from "./api"

export interface DownloadOptions {
  /** Called on 401 so the caller can send the user to the login page. */
  onUnauthorized?: () => void
}

function filenameFromDisposition(
  header: string | null,
  fallback: string
): string {
  if (!header) return fallback
  const match = /filename="?([^";]+)"?/i.exec(header)
  return match?.[1] ?? fallback
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === "object" &&
      body !== null &&
      "error" in body &&
      typeof body.error === "object" &&
      body.error !== null &&
      "message" in body.error &&
      typeof body.error.message === "string"
    ) {
      return body.error.message
    }
  } catch {
    // Non-JSON error body — fall through to the generic message.
  }
  return "دانلود خروجی ناموفق بود."
}

export async function downloadFile(
  url: string,
  fallbackName: string,
  options: DownloadOptions = {}
): Promise<void> {
  let response: Response
  try {
    response = await fetch(url, { credentials: "include" })
  } catch {
    throw new ApiRequestError(
      0,
      "دانلود خروجی ناموفق بود. اتصال را بررسی کنید."
    )
  }

  if (response.status === 401) {
    options.onUnauthorized?.()
    throw new ApiRequestError(401, "نیاز به ورود است")
  }
  if (!response.ok) {
    throw new ApiRequestError(response.status, await errorMessage(response))
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = filenameFromDisposition(
    response.headers.get("Content-Disposition"),
    fallbackName
  )
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Safari needs the URL alive until the download starts.
  setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}
