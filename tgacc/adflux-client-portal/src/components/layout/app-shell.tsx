"use client";

import React, { useState } from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { ChatWidget } from "@/components/chat/chat-widget";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-zinc-950 text-white">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
      <ChatWidget />
    </div>
  );
}
