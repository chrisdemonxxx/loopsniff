"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Users,
  CreditCard,
  DollarSign,
  Megaphone,
  Bot,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
  MessageCircle,
  MessagesSquare,
  TicketCheck,
  UserSearch,
  UsersRound,
  Link2,
  Bell,
  Settings2,
} from "lucide-react"
import { useState } from "react"

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Clients", href: "/clients", icon: Users },
  { label: "CRM", href: "/crm", icon: UserSearch },
  { label: "Conversations", href: "/conversations", icon: MessageCircle },
  { label: "Chat", href: "/chat", icon: MessagesSquare },
  { label: "Tickets", href: "/tickets", icon: TicketCheck },
  { label: "Accounts", href: "/accounts", icon: CreditCard },
  { label: "Finance", href: "/finance", icon: DollarSign },
  { label: "Outreach", href: "/outreach", icon: Megaphone },
  { label: "Team", href: "/team", icon: UsersRound },
  { label: "Affiliates", href: "/affiliates", icon: Link2 },
  { label: "Subscriptions", href: "/subscriptions", icon: CreditCard },
  { label: "Alerts", href: "/alerts", icon: Bell },
  { label: "Deposit Config", href: "/deposit-config", icon: Settings2 },
  { label: "Bot", href: "/bot", icon: Bot },
  { label: "Settings", href: "/settings", icon: Settings },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      {/* Mobile overlay backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside className={cn(
        "fixed left-0 top-0 z-50 h-screen border-r border-border bg-slate-950 transition-all duration-300",
        "lg:translate-x-0",
        collapsed ? "lg:w-16" : "lg:w-60",
        // Mobile: always full-width sidebar, slide in/out
        open ? "w-60 translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          {!collapsed && (
            <Link href="/dashboard" className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-md bg-emerald-500 flex items-center justify-center text-white font-bold text-sm">A</div>
              <span className="font-bold text-lg">AdFlux</span>
            </Link>
          )}
          {/* Close button on mobile */}
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-secondary text-muted-foreground lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
          {/* Collapse toggle on desktop */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:block p-1 rounded-md hover:bg-secondary text-muted-foreground"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
        <nav className="flex flex-col gap-1 p-2 mt-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/")
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {(!collapsed || open) && <span>{item.label}</span>}
              </Link>
            )
          })}
        </nav>
      </aside>
    </>
  )
}
