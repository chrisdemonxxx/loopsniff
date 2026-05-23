import React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-[360px] flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-[#0a0a0a] px-6 py-16 text-center",
        className
      )}
    >
      {icon && (
        <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full border border-white/10 text-zinc-300">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-white">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-zinc-400">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
