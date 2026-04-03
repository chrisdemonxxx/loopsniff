"use client"

import { useState } from "react"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { cn } from "@/lib/utils"

export function AdminShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="min-h-screen bg-zinc-950">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />
      <div
        className={cn(
          "transition-all duration-200",
          sidebarCollapsed ? "lg:pl-16" : "lg:pl-60"
        )}
      >
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  )
}
