"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/wallet", label: "Wallet", icon: Wallet2 },
  { href: "/accounts", label: "Accounts", icon: Layers },
  { href: "/ads-manager", label: "Ads Manager", icon: Megaphone },
  { href: "/topup", label: "Top Up", icon: CreditCard },
  { href: "/billing", label: "Billing", icon: Receipt },
  { href: "/spending", label: "Spending", icon: BarChart3 },
  { href: "/orders", label: "Orders", icon: Package },
  { href: "/support", label: "Support", icon: MessageCircle },
  { href: "/tickets", label: "Tickets", icon: TicketCheck },
  { href: "/affiliate", label: "Affiliate", icon: Users },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={cn(
          "fixed left-0 top-0 z-50 flex h-full w-64 flex-col border-r border-gray-800 bg-gray-950 transition-transform duration-200 lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-gray-800 px-6">
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-500">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold text-white">
              AdFlux<span className="text-blue-400"> Media</span>
            </span>
          </Link>
          <button onClick={onClose} className="text-gray-400 hover:text-white lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-blue-600/10 text-blue-400"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-gray-800 p-4">
          <div className="rounded-lg bg-gradient-to-r from-blue-600/20 to-violet-600/20 p-3">
            <p className="text-xs font-medium text-blue-300">Growth Plan</p>
            <p className="text-xs text-gray-400">5% commission rate</p>
          </div>
        </div>
      </aside>
    </>
  );
}
