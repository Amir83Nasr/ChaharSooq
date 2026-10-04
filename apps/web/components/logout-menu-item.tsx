"use client"

import { useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { LogOut } from "lucide-react"

import {
  SidebarMenuButton,
  useSidebar,
} from "@workspace/ui/components/sidebar"
import { api } from "@/lib/api"
import { LogoutDialog } from "@/components/logout-dialog"

export function LogoutMenuItem() {
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

  function requestOpen() {
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
  }

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

  return (
    <>
      <SidebarMenuButton
        className="group-data-[collapsible=icon]:mx-auto group-data-[collapsible=icon]:justify-center"
        render={<button type="button" onClick={requestOpen} />}
        tooltip="خروج"
        variant="destructive"
      >
        <LogOut />
        <span className="group-data-[collapsible=icon]:hidden">خروج</span>
      </SidebarMenuButton>
      <LogoutDialog
        open={open}
        onOpenChange={setOpen}
        onConfirm={onConfirm}
        pending={pending}
      />
    </>
  )
}
