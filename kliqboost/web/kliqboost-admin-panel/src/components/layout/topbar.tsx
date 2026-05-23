"use client"

import React from "react"
import Link from "next/link"
import { Menu } from "lucide-react"

interface TopbarProps {
  onMenuClick: () => void
}

export function Topbar({ onMenuClick }: TopbarProps) {
  return (
    <header className="flex h-12 items-center justify-between border-b border-white/[0.06] bg-black px-4 lg:px-6 sticky top-0 z-30">
      <button
        onClick={onMenuClick}
        aria-label="Open menu"
        className="text-zinc-400 hover:text-white lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="flex-1" />
      <div className="flex items-center gap-3 text-xs">
        <Link href="https://t.me/georgekatis" target="_blank" rel="noopener noreferrer" className="text-zinc-400 hover:text-white">
          Docs
        </Link>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-md border border-white/10 px-2 py-1 text-zinc-300 hover:bg-white/[0.05]"
          onClick={() => window.dispatchEvent(new CustomEvent("kliq:help"))}
        >
          Need help?
          <kbd className="ml-1 rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">H</kbd>
        </button>
      </div>
    </header>
  )
}
