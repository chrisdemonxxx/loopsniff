"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowRight, ArrowRightLeft, Loader2 } from "lucide-react"
import { useApi } from "@/lib/api"

type FunnelData = {
  total: number
  new: number
  contacted: number
  qualified: number
  proposal: number
  converted: number
  lost: number
}

type OutreachStats = {
  contacted: number
  dead: number
  new: number
}

const stageColors: Record<string, string> = {
  total: "#64748b",
  new: "#3b82f6",
  contacted: "#6366f1",
  qualified: "#a855f7",
  proposal: "#f59e0b",
  converted: "#10b981",
  lost: "#ef4444",
}

export default function OutreachPage() {
  const { data: funnel, loading: funnelLoading, error: funnelError, refetch: refetchFunnel } = useApi<FunnelData>("/outreach/funnel")
  const { data: stats, loading: statsLoading, error: statsError } = useApi<OutreachStats>("/outreach/sqlite/stats")

  const loading = funnelLoading || statsLoading
  const error = funnelError || statsError

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive mb-2">Failed to load outreach data</p>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button variant="outline" size="sm" onClick={refetchFunnel}>Retry</Button>
      </div>
    )
  }

  const funnelStages = funnel ? [
    { stage: "total", label: "Total", count: funnel.total },
    { stage: "new", label: "New", count: funnel.new },
    { stage: "contacted", label: "Contacted", count: funnel.contacted },
    { stage: "qualified", label: "Qualified", count: funnel.qualified },
    { stage: "proposal", label: "Proposal", count: funnel.proposal },
    { stage: "converted", label: "Converted", count: funnel.converted },
    { stage: "lost", label: "Lost", count: funnel.lost },
  ] : []

  const maxCount = funnelStages.length > 0 ? Math.max(...funnelStages.map(s => s.count), 1) : 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Outreach Funnel</h1>
        <Link href="/outreach/leads">
          <Button variant="outline" size="sm">
            Manage Leads <ArrowRight className="h-3 w-3 ml-2" />
          </Button>
        </Link>
      </div>

      {/* Funnel Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Conversion Funnel</CardTitle>
        </CardHeader>
        <CardContent>
          {funnelStages.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No funnel data yet</p>
          ) : (
          <div className="space-y-3">
            {funnelStages.map((stage, i) => {
              const widthPercent = Math.max(20, (stage.count / maxCount) * 100)
              const prevCount = i > 0 ? funnelStages[i - 1].count : 0
              const conversionRate = prevCount > 0 ? ((stage.count / prevCount) * 100).toFixed(1) : null
              return (
                <div key={stage.stage} className="flex items-center gap-4">
                  <span className="text-sm w-28 text-right text-muted-foreground">{stage.label}</span>
                  <div className="flex-1 relative">
                    <div
                      className="h-10 rounded-md flex items-center px-3 transition-all"
                      style={{
                        width: `${widthPercent}%`,
                        backgroundColor: (stageColors[stage.stage] || "#64748b") + "20",
                        borderLeft: `3px solid ${stageColors[stage.stage] || "#64748b"}`,
                      }}
                    >
                      <span className="text-sm font-bold">{stage.count}</span>
                    </div>
                  </div>
                  <div className="w-20 text-right">
                    {conversionRate && (
                      <div className="flex items-center gap-1 justify-end">
                        <ArrowRightLeft className="h-3 w-3 text-muted-foreground" />
                        <span className="text-xs text-muted-foreground">{conversionRate}%</span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Stage Transition Rates */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stage Transition Rates</CardTitle>
          </CardHeader>
          <CardContent>
            {funnelStages.length <= 1 ? (
              <p className="text-sm text-muted-foreground">No transition data yet</p>
            ) : (
            <div className="space-y-2">
              {funnelStages.slice(1).map((stage, i) => {
                const prevCount = funnelStages[i].count
                const rate = prevCount > 0 ? parseFloat(((stage.count / prevCount) * 100).toFixed(1)) : 0
                return (
                  <div key={stage.stage} className="flex items-center justify-between p-2 rounded-md bg-secondary/50">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-muted-foreground">{funnelStages[i].label}</span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span>{stage.label}</span>
                    </div>
                    <Badge variant={rate >= 70 ? 'success' : rate >= 50 ? 'warning' : 'destructive'}>
                      {rate}%
                    </Badge>
                  </div>
                )
              })}
            </div>
            )}
          </CardContent>
        </Card>

        {/* SQLite Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Lead Database Stats</CardTitle>
          </CardHeader>
          <CardContent>
            {stats ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-md bg-secondary/50">
                  <span className="text-sm text-muted-foreground">New Leads</span>
                  <span className="text-lg font-bold text-blue-400">{stats.new}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-md bg-secondary/50">
                  <span className="text-sm text-muted-foreground">Contacted</span>
                  <span className="text-lg font-bold text-violet-400">{stats.contacted}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-md bg-secondary/50">
                  <span className="text-sm text-muted-foreground">Dead / Unresponsive</span>
                  <span className="text-lg font-bold text-red-400">{stats.dead}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No stats available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold">{funnel?.total ?? 0}</div>
            <div className="text-xs text-muted-foreground">Total Leads</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-emerald-400">{funnel?.converted ?? 0}</div>
            <div className="text-xs text-muted-foreground">Converted</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-400">
              {funnel && funnel.total > 0 ? ((funnel.converted / funnel.total) * 100).toFixed(1) : "0.0"}%
            </div>
            <div className="text-xs text-muted-foreground">Overall Conversion</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-amber-400">{funnel?.proposal ?? 0}</div>
            <div className="text-xs text-muted-foreground">In Proposal</div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
