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
    <header className="animated-border-bottom sticky top-0 z-30 h-14 bg-zinc-950/70 backdrop-blur-2xl">
      <div className="flex h-full items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-3 min-w-0">
          {/* Hamburger menu for mobile */}
          <button
            onClick={onMenuClick}
            className="p-1.5 rounded-lg hover:bg-emerald-500/10 text-zinc-400 hover:text-emerald-400 transition-colors lg:hidden shrink-0"
          >
            <Menu className="h-5 w-5" />
          </button>
          {/* Breadcrumbs */}
          <div className="flex items-center gap-2 text-sm min-w-0 overflow-hidden">
            {crumbs.map((crumb, i) => (
              <span key={crumb.path} className="flex items-center gap-2 shrink-0">
                {i > 0 && (
                  <span className="h-1 w-1 rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500" />
                )}
                <span
                  className={
                    i === crumbs.length - 1
                      ? "text-white font-semibold truncate"
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
          <button className="search-glow hidden md:flex items-center gap-2 h-9 w-64 rounded-xl border border-zinc-800/60 bg-zinc-900/40 backdrop-blur-xl px-3 text-sm text-zinc-500 hover:text-zinc-300 transition-all duration-300">
            <Search className="h-4 w-4 shrink-0" />
            <span className="flex-1 text-left">Search...</span>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded-md border border-zinc-700/50 bg-zinc-800/80 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400">
              <Command className="h-3 w-3" />K
            </kbd>
          </button>

          {/* Notification bell with animated pulse */}
          <button className="relative p-2 rounded-lg hover:bg-emerald-500/10 text-zinc-400 hover:text-zinc-200 transition-colors">
            <Bell className="h-4 w-4" />
            <span className="notif-pulse absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center font-bold">
              3
            </span>
          </button>

          {/* User avatar with gradient ring */}
          <div className="flex items-center gap-2">
            <div className="avatar-glow-ring relative h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 via-cyan-400 to-emerald-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
              A
            </div>
            <div className="hidden md:block">
              <p className="text-sm font-semibold text-zinc-100">Admin</p>
            </div>
          </div>

          {/* Sign out */}
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="p-2 rounded-lg hover:bg-red-500/10 text-zinc-500 hover:text-red-400 transition-colors"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
