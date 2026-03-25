"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { Search, Loader2 } from "lucide-react"
import { useApi } from "@/lib/api"
import { formatDate } from "@/lib/utils"

type Lead = {
  username: string
  source: string
  status: string
  language: string
  niche: string
  budget_tier: string
  contacted_at: string | null
  contacted_by: string | null
  reply_count: number
  bant_score: number
  notes: string | null
}

const statusVariant: Record<string, string> = {
  new: "secondary",
  contacted: "info",
  replied: "info",
  engaged: "default",
  qualified: "default",
  hot: "warning",
  payment_sent: "warning",
  converted: "success",
  onboarded: "success",
  dead: "destructive",
}

export default function LeadsPage() {
  const { data: leads, loading, error, refetch } = useApi<Lead[]>("/outreach/sqlite/leads?limit=50")
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [selected, setSelected] = useState<string[]>([])
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)

  const list = leads ?? []

  const filtered = list.filter(l => {
    const matchesSearch = l.username.toLowerCase().includes(search.toLowerCase()) ||
      (l.niche ?? "").toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === "all" || l.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const toggleSelect = (username: string) => {
    setSelected(prev => prev.includes(username) ? prev.filter(s => s !== username) : [...prev, username])
  }

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
        <p className="text-destructive mb-2">Failed to load leads</p>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Lead Management</h1>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search leads..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
            </div>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "all", label: "All Statuses" },
                { value: "new", label: "New" },
                { value: "contacted", label: "Contacted" },
                { value: "replied", label: "Replied" },
                { value: "engaged", label: "Engaged" },
                { value: "qualified", label: "Qualified" },
                { value: "hot", label: "Hot" },
                { value: "payment_sent", label: "Payment Sent" },
                { value: "converted", label: "Converted" },
                { value: "onboarded", label: "Onboarded" },
                { value: "dead", label: "Dead" },
              ]}
              className="w-44"
            />
          </div>
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No leads found</p>
          ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <input type="checkbox" className="rounded border-border" onChange={(e) => {
                    if (e.target.checked) setSelected(filtered.map(l => l.username))
                    else setSelected([])
                  }} />
                </TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>BANT Score</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Contact</TableHead>
                <TableHead>Contacted By</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((lead) => (
                <TableRow key={lead.username}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selected.includes(lead.username)}
                      onChange={() => toggleSelect(lead.username)}
                      className="rounded border-border"
                    />
                  </TableCell>
                  <TableCell className="font-medium">{lead.username}</TableCell>
                  <TableCell><Badge variant="secondary">{lead.source}</Badge></TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 rounded-full bg-secondary overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${lead.bant_score ?? 0}%`,
                            backgroundColor: (lead.bant_score ?? 0) >= 80 ? '#10b981' : (lead.bant_score ?? 0) >= 60 ? '#f59e0b' : '#ef4444',
                          }}
                        />
                      </div>
                      <span className="text-xs">{lead.bant_score ?? 0}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={(statusVariant[lead.status] ?? "secondary") as any}>{(lead.status ?? "").replace('_', ' ')}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{lead.contacted_at ? formatDate(lead.contacted_at) : "—"}</TableCell>
                  <TableCell className="text-sm">{lead.contacted_by ?? "—"}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedLead(lead)}>View</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          )}
        </CardContent>
      </Card>

      {/* Lead Detail Modal */}
      <Modal open={!!selectedLead} onClose={() => setSelectedLead(null)} title="Lead Details">
        {selectedLead && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><span className="text-xs text-muted-foreground block">Username</span><span className="text-sm font-medium">{selectedLead.username}</span></div>
              <div><span className="text-xs text-muted-foreground block">Niche</span><span className="text-sm">{selectedLead.niche ?? "—"}</span></div>
              <div><span className="text-xs text-muted-foreground block">Source</span><Badge variant="secondary">{selectedLead.source}</Badge></div>
              <div><span className="text-xs text-muted-foreground block">Status</span><Badge variant={(statusVariant[selectedLead.status] ?? "secondary") as any}>{selectedLead.status}</Badge></div>
              <div><span className="text-xs text-muted-foreground block">BANT Score</span><span className="text-sm font-bold">{selectedLead.bant_score ?? 0}/100</span></div>
              <div><span className="text-xs text-muted-foreground block">Budget Tier</span><span className="text-sm">{selectedLead.budget_tier ?? "—"}</span></div>
              <div><span className="text-xs text-muted-foreground block">Language</span><span className="text-sm">{selectedLead.language ?? "—"}</span></div>
              <div><span className="text-xs text-muted-foreground block">Reply Count</span><span className="text-sm">{selectedLead.reply_count ?? 0}</span></div>
              <div><span className="text-xs text-muted-foreground block">Contacted By</span><span className="text-sm">{selectedLead.contacted_by ?? "—"}</span></div>
              <div><span className="text-xs text-muted-foreground block">Last Contact</span><span className="text-sm">{selectedLead.contacted_at ? formatDate(selectedLead.contacted_at) : "—"}</span></div>
            </div>
            <div><span className="text-xs text-muted-foreground block">Notes</span><span className="text-sm">{selectedLead.notes ?? "No notes"}</span></div>
          </div>
        )}
      </Modal>
    </div>
  )
}
