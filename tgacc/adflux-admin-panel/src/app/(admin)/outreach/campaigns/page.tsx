"use client"

import { useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Megaphone, Plus, Search, ExternalLink, Play, Pause, Trash2, Loader2, Users, Send, MessageSquare, BarChart3 } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { useToast } from "@/components/ui/toast"
import { formatPercent } from "@/lib/utils"

interface Campaign {
  id: string
  name: string
  status: string
  target_niche: string
  enrolled_count: number
  sent_count: number
  replied_count: number
  conversion_rate: number
  created_at: string
}

interface CampaignMetrics {
  active_campaigns: number
  total_enrolled: number
  total_sent: number
  overall_reply_rate: number
}

const statusVariant: Record<string, string> = {
  draft: "secondary",
  active: "success",
  paused: "warning",
  completed: "info",
  archived: "secondary",
}

export default function CampaignsPage() {
  const [search, setSearch] = useState("")
  const [statusTab, setStatusTab] = useState("all")
  const [deleting, setDeleting] = useState<string | null>(null)

  const token = useApiToken()
  const { toast } = useToast()
  const { data: campaigns, loading, error, refetch } = useApi<Campaign[]>("/outreach/campaigns?limit=100")
  const { data: metrics } = useApi<CampaignMetrics>("/outreach/metrics/campaigns")

  const list = campaigns ?? []

  const filtered = list.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.target_niche ?? "").toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusTab === "all" || c.status === statusTab
    return matchesSearch && matchesStatus
  })

  const handleTogglePause = async (campaign: Campaign) => {
    if (!token) return
    const newStatus = campaign.status === "active" ? "paused" : "active"
    try {
      await apiFetch(`/outreach/campaigns/${campaign.id}`, token, {
        method: "PUT",
        body: JSON.stringify({ status: newStatus }),
      })
      refetch()
    } catch (err: any) { toast(err.message || "Failed to update campaign", "error") }
  }

  const handleDelete = async (id: string) => {
    if (!token) return
    setDeleting(id)
    try {
      await apiFetch(`/outreach/campaigns/${id}`, token, { method: "DELETE" })
      refetch()
    } catch (err: any) { toast(err.message || "Failed to delete campaign", "error") }
    setDeleting(null)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading campaigns…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load campaigns: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="h-6 w-6" /> Campaigns
        </h1>
        <Link href="/outreach/campaigns/new">
          <Button><Plus className="h-4 w-4 mr-2" /> New Campaign</Button>
        </Link>
      </div>

      {/* Stats row */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4 pb-4">
              <span className="text-xs text-muted-foreground block">Active Campaigns</span>
              <span className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-emerald-400" /> {metrics.active_campaigns}
              </span>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <span className="text-xs text-muted-foreground block">Total Enrolled</span>
              <span className="text-xl font-bold flex items-center gap-2">
                <Users className="h-4 w-4 text-blue-400" /> {metrics.total_enrolled}
              </span>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <span className="text-xs text-muted-foreground block">Total Sent</span>
              <span className="text-xl font-bold flex items-center gap-2">
                <Send className="h-4 w-4 text-violet-400" /> {metrics.total_sent}
              </span>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <span className="text-xs text-muted-foreground block">Reply Rate</span>
              <span className="text-xl font-bold flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-amber-400" /> {formatPercent(metrics.overall_reply_rate)}
              </span>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Campaign table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search campaigns..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Status filter tabs */}
          <div className="inline-flex h-9 items-center justify-center rounded-lg bg-secondary p-1">
            {["all", "active", "paused", "draft", "completed", "archived"].map(tab => (
              <button
                key={tab}
                className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all ${statusTab === tab ? "bg-card text-foreground shadow" : "text-muted-foreground hover:text-foreground"}`}
                onClick={() => setStatusTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No campaigns found</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Target Niche</TableHead>
                  <TableHead>Enrolled</TableHead>
                  <TableHead>Sent</TableHead>
                  <TableHead>Replied</TableHead>
                  <TableHead>Conv. Rate</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((campaign) => (
                  <TableRow key={campaign.id}>
                    <TableCell className="font-medium">{campaign.name}</TableCell>
                    <TableCell>
                      <Badge variant={(statusVariant[campaign.status] ?? "secondary") as any}>
                        {campaign.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{campaign.target_niche ?? "—"}</TableCell>
                    <TableCell>{campaign.enrolled_count ?? 0}</TableCell>
                    <TableCell>{campaign.sent_count ?? 0}</TableCell>
                    <TableCell>{campaign.replied_count ?? 0}</TableCell>
                    <TableCell>{formatPercent(campaign.conversion_rate ?? 0)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Link href={`/outreach/campaigns/${campaign.id}`}>
                          <Button variant="ghost" size="icon" title="View">
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        </Link>
                        {(campaign.status === "active" || campaign.status === "paused") && (
                          <Button variant="ghost" size="icon" title={campaign.status === "active" ? "Pause" : "Resume"} onClick={() => handleTogglePause(campaign)}>
                            {campaign.status === "active" ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                          </Button>
                        )}
                        {campaign.status === "draft" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Delete"
                            onClick={() => handleDelete(campaign.id)}
                            disabled={deleting === campaign.id}
                          >
                            {deleting === campaign.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4 text-destructive" />}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
