"use client"

import { createContext, useContext, type ReactNode } from "react"

import { isAdmin, type SessionUser } from "@/lib/session"

type SessionContextValue = SessionUser & {
  /** True for the full-management role; read-only accounts get `false`. */
  canManage: boolean
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({
  user,
  children,
}: {
  user: SessionUser
  children: ReactNode
}) {
  const value: SessionContextValue = {
    ...user,
    canManage: isAdmin(user.role),
  }
  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  )
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext)
  if (!value) {
    throw new Error("useSession must be used within a SessionProvider.")
  }
  return value
}
