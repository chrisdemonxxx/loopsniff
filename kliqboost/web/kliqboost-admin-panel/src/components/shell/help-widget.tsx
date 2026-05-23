"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";

export function HelpWidget() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = () => setOpen((v) => !v);
    window.addEventListener("kliq:help", handler);
    const key = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "h" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const tag = (e.target as HTMLElement | null)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("kliq:help", handler);
      window.removeEventListener("keydown", key);
    };
  }, []);

  if (!open) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 w-72 rounded-xl border border-white/10 bg-[#0a0a0a] p-4 shadow-2xl">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-white">Need help?</h4>
        <button onClick={() => setOpen(false)} className="text-zinc-500 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>
      <p className="text-xs text-zinc-400">
        Reach the team directly on Telegram for fast support.
      </p>
      <div className="mt-3 flex flex-col gap-2">
        <Link
          href="https://t.me/georgekatis"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md bg-white px-3 py-1.5 text-center text-xs font-medium text-black hover:bg-zinc-200"
        >
          Message support
        </Link>
        <Link
          href="https://t.me/kliqboost_media"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-white/10 px-3 py-1.5 text-center text-xs text-zinc-300 hover:bg-white/5"
        >
          Join community
        </Link>
      </div>
    </div>
  );
}
