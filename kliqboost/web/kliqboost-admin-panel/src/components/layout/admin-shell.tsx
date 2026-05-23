"use client"

import { useState } from "react"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { HelpWidget } from "@/components/shell/help-widget"

export function AdminShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-black text-white">
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-60">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="px-6 py-6 lg:px-10 lg:py-8 min-h-[calc(100vh-3rem)]">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
      <HelpWidget />
    </div>
  )
}
