"use client";

import React, { useMemo } from "react";
import { Bell, LogOut, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";

interface TopbarProps {
  onMenuClick: () => void;
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const { data: session } = useSession();
  const user = session?.user;
  const name = user?.name || "User";
  const email = user?.email || "";
  const greeting = useMemo(() => getGreeting(), []);

  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("");

  const handleLogout = async () => {
    await signOut({ callbackUrl: "/login" });
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-zinc-800/50 bg-zinc-950/80 px-4 backdrop-blur-2xl lg:px-6">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="text-gray-400 hover:text-white lg:hidden"
        >
          <Menu className="h-6 w-6" />
        </button>

        <p className="hidden text-sm text-zinc-400 lg:block">
          {greeting},{" "}
          <span className="font-medium text-white">{name}</span>
        </p>
      </div>

      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5 text-gray-400" />
          <span
            className={cn(
              "absolute right-1 top-1 h-2 w-2 rounded-full bg-blue-500",
              "animate-pulse"
            )}
          />
        </Button>

        <div className="hidden items-center gap-3 sm:flex">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-violet-500 text-sm font-medium text-white shadow-lg shadow-blue-500/25">
            {initials}
          </div>
          <div className="text-sm">
            <p className="font-medium text-white">{name}</p>
            <p className="text-xs text-gray-400">{email}</p>
          </div>
        </div>

        <Button variant="ghost" size="icon" onClick={handleLogout}>
          <LogOut className="h-5 w-5 text-gray-400" />
        </Button>
      </div>
    </header>
  );
}
