"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { AlertTriangle, RefreshCw } from "lucide-react"

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Dashboard error:", error)
  }, [error])

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
      <div className="mx-auto max-w-md text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-destructive/10">
          <AlertTriangle className="h-7 w-7 text-destructive" />
        </div>
        <h2 className="text-xl font-semibold mb-2">Dashboard Error</h2>
        <p className="text-muted-foreground text-sm mb-6">
          Something went wrong while loading the dashboard. The rest of the admin panel is still accessible via the sidebar.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Button onClick={reset} variant="default" className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Retry
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-6 font-mono">
          {error.message || "Unknown error"}
        </p>
      </div>
    </div>
  )
}
