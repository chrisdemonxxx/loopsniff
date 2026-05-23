"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { AlertTriangle } from "lucide-react"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Unhandled error:", error)
  }, [error])

  const message = error?.message || "Unknown error"
  const stack = error?.stack || ""

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center max-w-md mx-auto p-8">
        <div className="mx-auto mb-4 h-14 w-14 rounded-xl bg-destructive/10 flex items-center justify-center">
          <AlertTriangle className="h-7 w-7 text-destructive" />
        </div>
        <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
        <p className="text-muted-foreground text-sm mb-4">
          An unexpected error occurred. Please try again or contact support if the problem persists.
        </p>
        <div className="mb-4 p-3 rounded-lg bg-destructive/5 border border-destructive/10 text-left">
          <p className="text-xs font-mono text-destructive break-all">{message}</p>
          {stack && (
            <pre className="mt-2 text-[10px] font-mono text-muted-foreground whitespace-pre-wrap break-all max-h-32 overflow-auto">
              {stack}
            </pre>
          )}
        </div>
        <Button onClick={reset} variant="outline">
          Try Again
        </Button>
      </div>
    </div>
  )
}
