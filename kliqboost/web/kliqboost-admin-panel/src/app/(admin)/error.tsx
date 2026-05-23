"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { AlertTriangle, RefreshCw } from "lucide-react"

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Admin section error:", error)
  }, [error])

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center max-w-md mx-auto p-8">
        <div className="mx-auto mb-4 h-14 w-14 rounded-xl bg-destructive/10 flex items-center justify-center">
          <AlertTriangle className="h-7 w-7 text-destructive" />
        </div>
        <h2 className="text-xl font-semibold mb-2">Admin Panel Error</h2>
        <p className="text-muted-foreground text-sm mb-4">
          Something went wrong in the admin panel. Other sections may still work.
        </p>
        <Button onClick={reset} variant="default" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Retry
        </Button>
      </div>
    </div>
  )
}
