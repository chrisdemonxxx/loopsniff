"use client"

import { usePathname } from "next/navigation"
import { Bell, Search, LogOut, Menu, Command } from "lucide-react"
import { signOut } from "next-auth/react"

const breadcrumbMap: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/clients": "Clients",
  "/accounts": "Accounts",
  "/finance": "Finance",
  "/finance/transactions": "Transactions",
  "/outreach": "Outreach",
  "/outreach/leads": "Leads",
  "/bot": "Bot",
  "/settings": "Settings",
}

interface TopbarProps {
  onMenuClick: () => void
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const pathname = usePathname()

  const getBreadcrumbs = () => {
    const parts = pathname.split("/").filter(Boolean)
    const crumbs: { label: string; path: string }[] = []
    let currentPath = ""
    for (const part of parts) {
      currentPath += `/${part}`
      const label = breadcrumbMap[currentPath] || part
      crumbs.push({ label, path: currentPath })
    }
    return crumbs
  }

  const crumbs = getBreadcrumbs()

  return (
    <header className="sticky top-0 z-30 h-14 border-b border-zinc-800/50 bg-zinc-950/80 backdrop-blur-2xl">
      <div className="flex h-full items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-3 min-w-0">
          {/* Hamburger menu for mobile */}
          <button
            onClick={onMenuClick}
            className="p-1 rounded-md hover:bg-zinc-800 text-zinc-400 lg:hidden shrink-0"
          >
            <Menu className="h-5 w-5" />
          </button>
          {/* Breadcrumbs */}
          <div className="flex items-center gap-2 text-sm min-w-0 overflow-hidden">
            {crumbs.map((crumb, i) => (
              <span key={crumb.path} className="flex items-center gap-2 shrink-0">
                {i > 0 && <span className="text-zinc-600">/</span>}
                <span
                  className={
                    i === crumbs.length - 1
                      ? "text-white font-medium truncate"
                      : "text-zinc-500 truncate"
                  }
                >
                  {crumb.label}
                </span>
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* ⌘K search trigger */}
          <button className="hidden md:flex items-center gap-2 h-9 w-64 rounded-lg border border-zinc-800/50 bg-zinc-900/50 backdrop-blur-sm px-3 text-sm text-zinc-500 hover:border-zinc-700 hover:text-zinc-400 transition-colors">
            <Search className="h-4 w-4 shrink-0" />
            <span className="flex-1 text-left">Search...</span>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400">
              <Command className="h-3 w-3" />K
            </kbd>
          </button>

          {/* Notification bell with pulse */}
          <button className="relative p-2 rounded-md hover:bg-zinc-800 text-zinc-400">
            <Bell className="h-4 w-4" />
            <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center animate-pulse">
              3
            </span>
          </button>

          {/* User avatar */}
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
              A
            </div>
            <div className="hidden md:block">
              <p className="text-sm font-medium text-zinc-200">Admin</p>
            </div>
          </div>

          {/* Sign out */}
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="p-2 rounded-md hover:bg-zinc-800 text-zinc-400"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
