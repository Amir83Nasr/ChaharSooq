/* Shared session shape — mirrors GET /api/v1/auth/me. */

import type { MeOut } from "./api-types"

export type { UserRole } from "./api-types"

export type SessionUser = MeOut

/** The env-managed top-level account. */
export function isOwner(role: SessionUser["role"]): boolean {
  return role === "owner"
}

/** Both management roles (`owner` and `admin`) can manage shop data. */
export function isAdmin(role: SessionUser["role"]): boolean {
  return role === "owner" || role === "admin"
}
