"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Layers,
  CreditCard,
  Receipt,
  BarChart3,
  MessageCircle,
  Settings,
  X,
  Zap,
  TicketCheck,
  Package,
  Megaphone,
  Wallet2,
  Users,
  Link2,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navSections = [
  {
    label: "OVERVIEW",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/wallet", label: "Wallet", icon: Wallet2 },
    ],
  },
  {
    label: "ADVERTISING",
    items: [
      { href: "/accounts", label: "Accounts", icon: Layers },
      { href: "/ads-manager", label: "Ads Manager", icon: Megaphone },
      { href: "/integrations", label: "Integrations", icon: Link2 },
    ],
  },
  {
    label: "BILLING",
    items: [
      { href: "/topup", label: "Top Up", icon: CreditCard },
      { href: "/billing", label: "Billing", icon: Receipt },
      { href: "/spending", label: "Spending", icon: BarChart3 },
      { href: "/orders", label: "Orders", icon: Package },
    ],
  },
  {
    label: "SUPPORT",
    items: [
      { href: "/support", label: "Support", icon: MessageCircle },
      { href: "/tickets", label: "Tickets", icon: TicketCheck },
    ],
  },
  {
    label: "OTHER",
    items: [
      { href: "/affiliate", label: "Affiliate", icon: Users },
      { href: "/ai-tools", label: "AI Tools", icon: Sparkles },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

  const sidebarContent = (
    <>
      <div className="flex h-16 items-center justify-between border-b border-zinc-800/50 px-6">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-500">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold text-white">
            AdFlux<span className="text-blue-400"> Media</span>
          </span>
        </Link>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white lg:hidden"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive =
                  pathname === item.href ||
                  pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "border-l-[3px] border-blue-500 bg-blue-500/10 text-blue-400"
                        : "border-l-[3px] border-transparent text-gray-400 hover:bg-zinc-800/50 hover:text-white"
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-zinc-800/50 p-4">
        <div className="glass-card rounded-lg bg-gradient-to-r from-blue-600/20 to-violet-600/20 p-3">
          <p className="text-xs font-medium text-blue-300">Growth Plan</p>
          <p className="text-xs text-gray-400">5% commission rate</p>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden h-full w-64 flex-col border-r border-zinc-800/50 bg-zinc-950/95 backdrop-blur-xl lg:flex">
        {sidebarContent}
      </aside>

      {/* Mobile overlay + slide sidebar */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />
            <motion.aside
              className="fixed left-0 top-0 z-50 flex h-full w-64 flex-col border-r border-zinc-800/50 bg-zinc-950/95 backdrop-blur-xl lg:hidden"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
