export default function AdminLoading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        Loading admin panel…
      </div>
    </div>
  )
}
