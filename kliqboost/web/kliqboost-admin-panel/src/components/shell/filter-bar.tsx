"use client";

import React from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface FilterBarProps {
  search?: string;
  onSearchChange?: (value: string) => void;
  placeholder?: string;
  children?: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}

export function FilterBar({
  search,
  onSearchChange,
  placeholder = "Search…",
  children,
  right,
  className,
}: FilterBarProps) {
  return (
    <div className={cn("mb-6 flex flex-wrap items-center gap-2", className)}>
      <div className="relative flex-1 min-w-[240px]">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
        <input
          value={search ?? ""}
          onChange={(e) => onSearchChange?.(e.target.value)}
          placeholder={placeholder}
          className="h-9 w-full rounded-md border border-white/10 bg-[#0a0a0a] pl-9 pr-3 text-sm text-white placeholder:text-zinc-500 focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
        />
      </div>
      {children}
      {right && <div className="ml-auto flex items-center gap-2">{right}</div>}
    </div>
  );
}
