"use client"

import { usePathname } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Bell, Search, LogOut, Menu } from "lucide-react"
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
    <header className="sticky top-0 z-30 h-14 border-b border-border bg-slate-950/80 backdrop-blur-sm">
      <div className="flex h-full items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-3 min-w-0">
          {/* Hamburger menu for mobile */}
          <button
            onClick={onMenuClick}
            className="p-1 rounded-md hover:bg-secondary text-muted-foreground lg:hidden shrink-0"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2 text-sm min-w-0 overflow-hidden">
            {crumbs.map((crumb, i) => (
              <span key={crumb.path} className="flex items-center gap-2 shrink-0">
                {i > 0 && <span className="text-muted-foreground">/</span>}
                <span className={i === crumbs.length - 1 ? "text-foreground truncate" : "text-muted-foreground truncate"}>
                  {crumb.label}
                </span>
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-4 shrink-0">
          <div className="relative hidden md:block">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search..."
              className="h-9 w-64 rounded-md border border-border bg-secondary pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <button className="relative p-2 rounded-md hover:bg-secondary text-muted-foreground">
            <Bell className="h-4 w-4" />
            <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-destructive text-[10px] text-white flex items-center justify-center">3</span>
          </button>
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-emerald-500 flex items-center justify-center text-white text-xs font-bold shrink-0">A</div>
            <div className="hidden md:block">
              <p className="text-sm font-medium">Admin</p>
              <Badge variant="default" className="text-[10px] py-0">super_admin</Badge>
            </div>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
