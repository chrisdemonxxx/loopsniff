"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Modal } from "@/components/ui/modal"
import { Select } from "@/components/ui/select"
import { ArrowLeft, Loader2, Upload, Users, Send, Clock, Target, Trophy, MessageSquare } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatDate, formatPercent } from "@/lib/utils"

interface Campaign {
  id: string
  name: string
  description: string
  status: string
  target_niche: string
  daily_send_cap: number
  send_window_start: number
  send_window_end: number
  sequence?: Sequence
  created_at: string
  updated_at: string
}

interface Sequence {
  id: string
  name: string
  steps: SequenceStep[]
}

interface SequenceStep {
  step_order: number
  delay_hours: number
  step_type: string
  template_a: string
  template_b?: string
}

interface EnrolledLead {
  tg_username: string
  tg_user_id: string | null
  status: string
  current_step: number
  ab_variant: string
  assigned_account: string | null
  last_sent_at: string | null
  replied_at: string | null
}

interface ABResult {
  step_order: number
  variant_a: { sent: number; replied: number; rate: number }
  variant_b: { sent: number; replied: number; rate: number }
  winner: string | null
}

const statusVariant: Record<string, string> = {
  draft: "secondary",
  active: "success",
  paused: "warning",
  completed: "info",
  archived: "secondary",
}

const leadStatusVariant: Record<string, string> = {
  pending: "secondary",
  active: "default",
  replied: "success",
  converted: "success",
  failed: "destructive",
  unsubscribed: "destructive",
}

export default function CampaignDetailPage() {
  const params = useParams()
  const id = params.id as string
  const token = useApiToken()

  const [leadStatusFilter, setLeadStatusFilter] = useState("all")
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadText, setUploadText] = useState("")
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data: campaign, loading, error, refetch } = useApi<Campaign>(`/outreach/campaigns/${id}`)
  const { data: leads, loading: leadsLoading, refetch: refetchLeads } = useApi<EnrolledLead[]>(`/outreach/campaigns/${id}/leads`)
  const { data: abResults } = useApi<ABResult[]>(`/outreach/campaigns/${id}/ab-results`)

  const filteredLeads = (leads ?? []).filter(l =>
    leadStatusFilter === "all" || l.status === leadStatusFilter
  )

  const handleUploadLeads = async () => {
    if (!token || !uploadText.trim()) return
    setUploading(true)
    setUploadError(null)
    try {
      const parsed = JSON.parse(uploadText.trim())
      const payload = Array.isArray(parsed) ? { leads: parsed } : parsed
      await apiFetch(`/outreach/campaigns/${id}/upload-leads`, token, {
        method: "POST",
        body: JSON.stringify(payload),
      })
      setUploadOpen(false)
      setUploadText("")
      refetchLeads()
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload leads")
    } finally {
      setUploading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading campaign…</span>
      </div>
    )
  }

  if (error || !campaign) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load campaign: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/outreach/campaigns">
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{campaign.name}</h1>
          {campaign.description && (
            <p className="text-sm text-muted-foreground mt-1">{campaign.description}</p>
          )}
        </div>
        <Badge variant={(statusVariant[campaign.status] ?? "secondary") as any} className="text-sm">
          {campaign.status}
        </Badge>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="leads">Leads</TabsTrigger>
          <TabsTrigger value="ab-results">A/B Results</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview">
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-4 pb-4">
                  <span className="text-xs text-muted-foreground block">Status</span>
                  <Badge variant={(statusVariant[campaign.status] ?? "secondary") as any} className="mt-1">
                    {campaign.status}
                  </Badge>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 pb-4">
                  <span className="text-xs text-muted-foreground block">Target Niche</span>
                  <span className="text-sm font-medium flex items-center gap-1 mt-1">
                    <Target className="h-3.5 w-3.5 text-blue-400" /> {campaign.target_niche ?? "—"}
                  </span>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 pb-4">
                  <span className="text-xs text-muted-foreground block">Daily Send Cap</span>
                  <span className="text-sm font-medium flex items-center gap-1 mt-1">
                    <Send className="h-3.5 w-3.5 text-violet-400" /> {campaign.daily_send_cap ?? "—"}
                  </span>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 pb-4">
                  <span className="text-xs text-muted-foreground block">Send Window</span>
                  <span className="text-sm font-medium flex items-center gap-1 mt-1">
                    <Clock className="h-3.5 w-3.5 text-amber-400" />
                    {campaign.send_window_start ?? 0}:00 – {campaign.send_window_end ?? 23}:00
                  </span>
                </CardContent>
              </Card>
            </div>

            {/* Sequence steps */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" /> Sequence Steps
                </CardTitle>
              </CardHeader>
              <CardContent>
                {campaign.sequence?.steps && campaign.sequence.steps.length > 0 ? (
                  <div className="space-y-3">
                    {campaign.sequence.steps
                      .sort((a, b) => a.step_order - b.step_order)
                      .map((step, idx) => (
                        <div key={idx} className="rounded-lg border border-border p-4 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium">Step {step.step_order}</span>
                            <div className="flex items-center gap-2">
                              <Badge variant="secondary">{step.step_type}</Badge>
                              <span className="text-xs text-muted-foreground">
                                Delay: {step.delay_hours}h
                              </span>
                            </div>
                          </div>
                          <div>
                            <span className="text-xs text-muted-foreground block mb-1">Template A</span>
                            <p className="text-sm bg-secondary/50 rounded p-2 whitespace-pre-wrap">{step.template_a}</p>
                          </div>
                          {step.template_b && (
                            <div>
                              <span className="text-xs text-muted-foreground block mb-1">Template B</span>
                              <p className="text-sm bg-secondary/50 rounded p-2 whitespace-pre-wrap">{step.template_b}</p>
                            </div>
                          )}
                        </div>
                      ))}
                  </div>
                ) : (
                  <p className="text-center py-6 text-muted-foreground">No sequence steps configured</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Leads Tab */}
        <TabsContent value="leads">
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Users className="h-4 w-4" /> Enrolled Leads
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Select
                    value={leadStatusFilter}
                    onChange={(e) => setLeadStatusFilter(e.target.value)}
                    options={[
                      { value: "all", label: "All Statuses" },
                      { value: "pending", label: "Pending" },
                      { value: "active", label: "Active" },
                      { value: "replied", label: "Replied" },
                      { value: "converted", label: "Converted" },
                      { value: "failed", label: "Failed" },
                      { value: "unsubscribed", label: "Unsubscribed" },
                    ]}
                    className="w-40"
                  />
                  <Button size="sm" onClick={() => setUploadOpen(true)}>
                    <Upload className="h-4 w-4 mr-2" /> Upload Leads
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {leadsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : filteredLeads.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No leads enrolled</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Username</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Current Step</TableHead>
                      <TableHead>A/B Variant</TableHead>
                      <TableHead>Assigned Account</TableHead>
                      <TableHead>Last Sent</TableHead>
                      <TableHead>Replied</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredLeads.map((lead) => (
                      <TableRow key={lead.tg_username}>
                        <TableCell className="font-medium">@{lead.tg_username}</TableCell>
                        <TableCell>
                          <Badge variant={(leadStatusVariant[lead.status] ?? "secondary") as any}>
                            {lead.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{lead.current_step ?? "—"}</TableCell>
                        <TableCell>
                          {lead.ab_variant ? (
                            <Badge variant={lead.ab_variant === "A" ? "default" : "info"}>{lead.ab_variant}</Badge>
                          ) : "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-xs">{lead.assigned_account ?? "—"}</TableCell>
                        <TableCell className="text-muted-foreground text-xs">{lead.last_sent_at ? formatDate(lead.last_sent_at) : "—"}</TableCell>
                        <TableCell className="text-muted-foreground text-xs">{lead.replied_at ? formatDate(lead.replied_at) : "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* A/B Results Tab */}
        <TabsContent value="ab-results">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Trophy className="h-4 w-4" /> A/B Test Results
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!abResults || abResults.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No A/B test results available</p>
              ) : (
                <div className="space-y-4">
                  {abResults.map((result) => (
                    <div key={result.step_order} className="rounded-lg border border-border p-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-medium">Step {result.step_order}</span>
                        {result.winner && (
                          <Badge variant="success">Winner: Variant {result.winner}</Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className={`rounded-lg p-3 ${result.winner === "A" ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-secondary/50"}`}>
                          <span className="text-xs text-muted-foreground block mb-2">Variant A</span>
                          <div className="grid grid-cols-3 gap-2 text-center">
                            <div>
                              <span className="text-xs text-muted-foreground block">Sent</span>
                              <span className="text-sm font-bold">{result.variant_a.sent}</span>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground block">Replied</span>
                              <span className="text-sm font-bold">{result.variant_a.replied}</span>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground block">Rate</span>
                              <span className="text-sm font-bold">{formatPercent(result.variant_a.rate)}</span>
                            </div>
                          </div>
                        </div>
                        <div className={`rounded-lg p-3 ${result.winner === "B" ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-secondary/50"}`}>
                          <span className="text-xs text-muted-foreground block mb-2">Variant B</span>
                          <div className="grid grid-cols-3 gap-2 text-center">
                            <div>
                              <span className="text-xs text-muted-foreground block">Sent</span>
                              <span className="text-sm font-bold">{result.variant_b.sent}</span>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground block">Replied</span>
                              <span className="text-sm font-bold">{result.variant_b.replied}</span>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground block">Rate</span>
                              <span className="text-sm font-bold">{formatPercent(result.variant_b.rate)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Upload Leads Modal */}
      <Modal open={uploadOpen} onClose={() => { setUploadOpen(false); setUploadError(null) }} title="Upload Leads">
        <div className="space-y-4">
          {uploadError && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{uploadError}</div>
          )}
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
              Leads (JSON array)
            </label>
            <textarea
              className="flex w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[160px] font-mono"
              placeholder={`[{"tg_username": "user1", "tg_user_id": "12345"}, ...]`}
              value={uploadText}
              onChange={(e) => setUploadText(e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Paste a JSON array of leads with tg_username and optional tg_user_id fields.
            </p>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => { setUploadOpen(false); setUploadError(null) }} className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleUploadLeads} className="flex-1" disabled={uploading || !uploadText.trim()}>
              {uploading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Uploading…</> : <><Upload className="h-4 w-4 mr-2" /> Upload</>}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
