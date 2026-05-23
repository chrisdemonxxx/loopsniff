"use client"

import { SessionProvider } from "next-auth/react"
import { ToastProvider } from "@/components/ui/toast"

export function Providers({
  children,
  session,
}: {
  children: React.ReactNode
  session?: any
}) {
  return (
    <SessionProvider session={session}>
      <ToastProvider>{children}</ToastProvider>
    </SessionProvider>
  )
}
