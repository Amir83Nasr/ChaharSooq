/* Shared session shape — mirrors GET /api/v1/auth/me. */

import type { MeOut } from "./api-types"

export type { UserRole } from "./api-types"

export type SessionUser = MeOut

export function isAdmin(role: SessionUser["role"]): boolean {
  return role === "admin"
}
