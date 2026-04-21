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
import { motion, AnimatePresence } from "framer-motion"

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
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-md lg:hidden"
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      <motion.aside
        animate={{ width: open ? 240 : collapsed ? 64 : 240 }}
        transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
        className={cn(
          "fixed left-0 top-0 z-50 h-screen flex flex-col sidebar-gradient-bg overflow-hidden",
          "border-r border-emerald-500/10",
          "lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Gradient accent strip on left edge */}
        <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-gradient-to-b from-emerald-400 via-cyan-500 to-emerald-400/20 z-10" />

        {/* Floating orbs for depth */}
        <div className="absolute top-20 left-6 w-32 h-32 rounded-full bg-emerald-500/5 blur-3xl floating-orb pointer-events-none" />
        <div className="absolute bottom-32 right-2 w-24 h-24 rounded-full bg-cyan-500/5 blur-3xl floating-orb-slow pointer-events-none" />

        {/* Logo */}
        <div className="relative flex h-16 items-center justify-between border-b border-emerald-500/10 px-4">
          {showLabels && (
            <Link href="/dashboard" className="flex items-center gap-3">
              <div className="logo-ring relative h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 glow-emerald flex items-center justify-center text-white font-bold text-sm shrink-0">
                A
              </div>
              <motion.span
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                className="font-bold text-lg"
              >
                <span className="text-white">Ad</span>
                <span className="text-gradient">Flux</span>
              </motion.span>
            </Link>
          )}
          {collapsed && !open && (
            <Link href="/dashboard" className="mx-auto">
              <div className="logo-ring relative h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 glow-emerald flex items-center justify-center text-white font-bold text-sm">
                A
              </div>
            </Link>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-emerald-500/10 text-zinc-400 hover:text-emerald-400 transition-colors lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation */}
        {/* min-h-0 is required so flex-1 can shrink below intrinsic content size
            and overflow-y-auto actually scrolls inside the h-screen column. */}
        <nav className="relative z-10 flex-1 min-h-0 overflow-y-auto overflow-x-hidden py-4 px-2 space-y-5">
          {navSections.map((section, sIdx) => (
            <div key={section.label}>
              {/* Gradient divider between sections */}
              {sIdx > 0 && <div className="gradient-divider mx-3 mb-3" />}

              {showLabels && (
                <p className="px-3 mb-2 text-[10px] font-bold tracking-[0.2em] text-gradient uppercase">
                  {section.label}
                </p>
              )}
              {!showLabels && (
                <div className="mx-auto mb-2 gradient-divider w-6" />
              )}
              <div className="space-y-1">
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
                        "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                        isActive
                          ? "nav-active-glow text-emerald-300"
                          : "text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
                      )}
                    >
                      <item.icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors",
                          isActive ? "text-emerald-400" : "text-zinc-500"
                        )}
                      />
                      {showLabels && (
                        <motion.span layout="position">{item.label}</motion.span>
                      )}
                      {/* Active indicator dot */}
                      {isActive && (
                        <motion.div
                          layoutId="sidebar-active"
                          className="absolute right-2 h-1.5 w-1.5 rounded-full bg-emerald-400 glow-emerald"
                          transition={{ type: "spring", stiffness: 350, damping: 30 }}
                        />
                      )}
                    </Link>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="relative z-10 border-t border-emerald-500/10 p-3">
          {showLabels ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="avatar-glow-ring relative h-9 w-9 rounded-full bg-gradient-to-br from-emerald-400 via-cyan-400 to-emerald-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  SA
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-zinc-100 truncate">Super Admin</p>
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
                    <Shield className="h-3 w-3" />
                    Admin
                  </span>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => onCollapsedChange(!collapsed)}
                className="hidden lg:flex p-1.5 rounded-lg hover:bg-emerald-500/10 text-zinc-500 hover:text-emerald-400 transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </motion.button>
            </div>
          ) : (
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => onCollapsedChange(false)}
              className="hidden lg:flex mx-auto p-1.5 rounded-lg hover:bg-emerald-500/10 text-zinc-500 hover:text-emerald-400 transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </motion.button>
          )}
        </div>
      </motion.aside>
    </>
  )
}
