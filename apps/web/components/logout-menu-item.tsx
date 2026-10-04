"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useRouter } from "next/navigation"
import { LogOut } from "lucide-react"

import {
  SidebarMenuButton,
  useSidebar,
} from "@workspace/ui/components/sidebar"
import { api } from "@/lib/api"
import { LogoutDialog } from "@/components/logout-dialog"

type LogoutContextValue = {
  requestLogout: () => void
}

const LogoutContext = createContext<LogoutContextValue | null>(null)

function useLogout() {
  const context = useContext(LogoutContext)
  if (!context) {
    throw new Error("useLogout must be used within a LogoutProvider.")
  }
  return context
}

// State lives above the mobile sidebar sheet: closing the sheet unmounts
// its children, which used to kill the pending dialog open timer.
export function LogoutProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { isMobile, setOpenMobile } = useSidebar()
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(false)
  const openTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(
    () => () => {
      if (openTimer.current) clearTimeout(openTimer.current)
    },
    []
  )

  const requestLogout = useCallback(() => {
    // The mobile sidebar is itself a modal sheet. Let it finish closing
    // before opening the confirmation drawer so focus transfers cleanly.
    if (!isMobile) {
      setOpen(true)
      return
    }
    setOpenMobile(false)
    if (openTimer.current) clearTimeout(openTimer.current)
    openTimer.current = setTimeout(() => {
      setOpen(true)
      openTimer.current = null
    }, 550)
  }, [isMobile, setOpenMobile])

  async function onConfirm() {
    setPending(true)
    try {
      await api.logout()
    } catch {
      // Server already cleared or session expired — still leave the shell.
    } finally {
      setPending(false)
    }
    setOpen(false)
    router.push("/login")
    router.refresh()
  }

  const value = useMemo(() => ({ requestLogout }), [requestLogout])

  return (
    <LogoutContext.Provider value={value}>
      {children}
      <LogoutDialog
        open={open}
        onOpenChange={setOpen}
        onConfirm={onConfirm}
        pending={pending}
      />
    </LogoutContext.Provider>
  )
}

export function LogoutMenuItem() {
  const { requestLogout } = useLogout()

  return (
    <SidebarMenuButton
      className="group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:justify-center"
      render={<button type="button" onClick={requestLogout} />}
      tooltip="خروج"
      variant="destructive"
    >
      <LogOut />
      <span className="group-data-[collapsible=icon]:hidden">خروج</span>
    </SidebarMenuButton>
  )
}
