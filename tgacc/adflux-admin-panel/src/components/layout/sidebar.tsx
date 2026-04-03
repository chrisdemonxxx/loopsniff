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
  Shield,
} from "lucide-react"
import { motion } from "framer-motion"

const navSections = [
  {
    label: "OVERVIEW",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "CLIENTS",
    items: [
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
      { label: "Deposit Config", href: "/deposit-config", icon: Settings2 },
      { label: "Bot", href: "/bot", icon: Bot },
      { label: "Settings", href: "/settings", icon: Settings },
    ],
  },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

export function Sidebar({ open, onClose, collapsed, onCollapsedChange }: SidebarProps) {
  const pathname = usePathname()
  const showLabels = !collapsed || open

  return (
    <>
      {/* Mobile overlay backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      <motion.aside
        animate={{ width: open ? 240 : collapsed ? 64 : 240 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className={cn(
          "fixed left-0 top-0 z-50 h-screen flex flex-col",
          "bg-zinc-950/95 backdrop-blur-xl border-r border-zinc-800/50",
          "lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center justify-between border-b border-zinc-800/50 px-4">
          {showLabels && (
            <Link href="/dashboard" className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-md bg-emerald-500 glow-emerald flex items-center justify-center text-white font-bold text-sm shrink-0">
                A
              </div>
              <span className="font-bold text-lg">
                <span className="text-white">AdFlux</span>
                <span className="text-emerald-400"> Media</span>
              </span>
            </Link>
          )}
          {collapsed && !open && (
            <Link href="/dashboard" className="mx-auto">
              <div className="h-7 w-7 rounded-md bg-emerald-500 glow-emerald flex items-center justify-center text-white font-bold text-sm">
                A
              </div>
            </Link>
          )}
          {/* Close button on mobile */}
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-zinc-800 text-zinc-400 lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2 space-y-4">
          {navSections.map((section) => (
            <div key={section.label}>
              {showLabels && (
                <p className="px-3 mb-1.5 text-[10px] font-semibold tracking-widest text-zinc-500 uppercase">
                  {section.label}
                </p>
              )}
              {!showLabels && (
                <div className="mx-auto mb-1.5 h-px w-6 bg-zinc-800" />
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive =
                    pathname === item.href ||
                    pathname.startsWith(item.href + "/")
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      title={collapsed && !open ? item.label : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "border-l-[3px] border-emerald-500 bg-emerald-500/10 text-emerald-400"
                          : "border-l-[3px] border-transparent text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                      )}
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      {showLabels && <span>{item.label}</span>}
                    </Link>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="border-t border-zinc-800/50 p-3">
          {showLabels ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  SA
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-200 truncate">Super Admin</p>
                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-400">
                    <Shield className="h-3 w-3" />
                    Admin
                  </span>
                </div>
              </div>
              <button
                onClick={() => onCollapsedChange(!collapsed)}
                className="hidden lg:flex p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => onCollapsedChange(false)}
              className="hidden lg:flex mx-auto p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </motion.aside>
    </>
  )
}
