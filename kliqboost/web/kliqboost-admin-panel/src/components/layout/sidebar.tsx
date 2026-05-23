"use client"

import React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession, signOut } from "next-auth/react"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Users,
  CreditCard,
  DollarSign,
  Megaphone,
  Bot,
  Settings,
  ChevronDown,
  X,
  MessageCircle,
  MessagesSquare,
  TicketCheck,
  UserSearch,
  UsersRound,
  Link2,
  Bell,
  Settings2,
  LogOut,
} from "lucide-react"

const navSections: {
  label?: string
  items: { label: string; href: string; icon: React.ComponentType<{ className?: string }> }[]
}[] = [
  {
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "Clients", href: "/clients", icon: Users },
      { label: "CRM", href: "/crm", icon: UserSearch },
      { label: "Conversations", href: "/conversations", icon: MessageCircle },
      { label: "Chat", href: "/chat", icon: MessagesSquare },
      { label: "Tickets", href: "/tickets", icon: TicketCheck },
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      { label: "Accounts", href: "/accounts", icon: CreditCard },
      { label: "Finance", href: "/finance", icon: DollarSign },
      { label: "Outreach", href: "/outreach", icon: Megaphone },
    ],
  },
  {
    label: "MANAGEMENT",
    items: [
      { label: "Team", href: "/team", icon: UsersRound },
      { label: "Affiliates", href: "/affiliates", icon: Link2 },
      { label: "Subscriptions", href: "/subscriptions", icon: CreditCard },
    ],
  },
  {
    label: "SYSTEM",
    items: [
      { label: "Alerts", href: "/alerts", icon: Bell },
      { label: "Deposit config", href: "/deposit-config", icon: Settings2 },
      { label: "Bot", href: "/bot", icon: Bot },
      { label: "Settings", href: "/settings", icon: Settings },
    ],
  },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
  collapsed?: boolean
  onCollapsedChange?: (collapsed: boolean) => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname()
  const { data: session } = useSession()
  const user = session?.user as { name?: string | null; email?: string | null } | undefined
  const userName = user?.name || "Admin"
  const email = user?.email || ""
  const initials =
    userName
      .split(/\s+/)
      .map((p) => p[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "A"

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-50 flex h-screen w-60 flex-col bg-black border-r border-white/[0.06]",
        "transition-transform duration-200",
        "lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}
    >
      {/* User pill */}
      <div className="px-3 pt-4 pb-3">
        <div className="flex items-center justify-between gap-2 rounded-lg px-2 py-2 hover:bg-white/5 cursor-pointer">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold text-black">
              {initials}
            </div>
            <span className="truncate text-sm font-medium text-white">{userName}</span>
          </div>
          <ChevronDown className="h-4 w-4 flex-shrink-0 text-zinc-500" />
        </div>
      </div>

      <button
        onClick={onClose}
        className="absolute right-2 top-2 rounded p-2 text-zinc-400 hover:text-white lg:hidden"
        aria-label="Close menu"
      >
        <X className="h-4 w-4" />
      </button>

      <nav className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-3 pb-4">
        {navSections.map((section, sIdx) => (
          <div key={sIdx} className={sIdx > 0 ? "mt-5" : ""}>
            {section.label && (
              <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive =
                  pathname === item.href || pathname.startsWith(item.href + "/")
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors",
                      isActive
                        ? "bg-white/[0.06] text-white"
                        : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
                    )}
                  >
                    <item.icon className="h-4 w-4 flex-shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-white/[0.06] p-3">
        <div className="flex items-center justify-between gap-2 rounded-md px-2 py-2 hover:bg-white/5">
          <span className="truncate text-xs text-zinc-400">{email || "—"}</span>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-zinc-500 hover:text-white"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
