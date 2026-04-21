"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { Search, Plus, Loader2, X } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatDate } from "@/lib/utils"

interface CrmLead {
  id: string
  name: string
  company: string
  status: string
  priority: string
  bant_score: number
  source: string
  assigned_bdm: string | null
  last_contact: string | null
  email: string | null
  phone: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

const statusVariant: Record<string, string> = {
  new: "secondary",
  contacted: "info",
  qualified: "default",
  proposal: "warning",
  negotiation: "warning",
  won: "success",
  lost: "destructive",
}

const priorityVariant: Record<string, string> = {
  low: "secondary",
  medium: "info",
  high: "warning",
  urgent: "destructive",
}

export default function CrmPage() {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [priorityFilter, setPriorityFilter] = useState("all")
  const [sourceFilter, setSourceFilter] = useState("all")
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [detailLead, setDetailLead] = useState<CrmLead | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const token = useApiToken()
  const { data: leads, loading, error, refetch } = useApi<CrmLead[]>("/crm/leads?limit=50")

  // Form state
  const [formName, setFormName] = useState("")
  const [formCompany, setFormCompany] = useState("")
  const [formEmail, setFormEmail] = useState("")
  const [formPhone, setFormPhone] = useState("")
  const [formSource, setFormSource] = useState("website")
  const [formPriority, setFormPriority] = useState("medium")
  const [formNotes, setFormNotes] = useState("")

  const resetForm = () => {
    setFormName("")
    setFormCompany("")
    setFormEmail("")
    setFormPhone("")
    setFormSource("website")
    setFormPriority("medium")
    setFormNotes("")
    setFormError(null)
  }

  const handleAddLead = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setFormError(null)
    try {
      await apiFetch("/crm/leads", token, {
        method: "POST",
        body: JSON.stringify({
          name: formName,
          company: formCompany,
          email: formEmail,
          phone: formPhone,
          source: formSource,
          priority: formPriority,
          notes: formNotes,
        }),
      })
      setAddModalOpen(false)
      resetForm()
      refetch()
    } catch (err: any) {
      setFormError(err.message || "Failed to add lead")
    } finally {
      setSubmitting(false)
    }
  }

  const list = leads ?? []

  const filtered = list.filter((l) => {
    const matchesSearch =
      l.name.toLowerCase().includes(search.toLowerCase()) ||
      (l.company ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (l.email ?? "").toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === "all" || l.status === statusFilter
    const matchesPriority = priorityFilter === "all" || l.priority === priorityFilter
    const matchesSource = sourceFilter === "all" || l.source === sourceFilter
    return matchesSearch && matchesStatus && matchesPriority && matchesSource
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading leads…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load CRM leads: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">CRM Leads</h1>
        <Button onClick={() => setAddModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" /> Add Lead
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search leads..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "all", label: "All Statuses" },
                { value: "new", label: "New" },
                { value: "contacted", label: "Contacted" },
                { value: "qualified", label: "Qualified" },
                { value: "proposal", label: "Proposal" },
                { value: "negotiation", label: "Negotiation" },
                { value: "won", label: "Won" },
                { value: "lost", label: "Lost" },
              ]}
              className="w-40"
            />
            <Select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              options={[
                { value: "all", label: "All Priorities" },
                { value: "low", label: "Low" },
                { value: "medium", label: "Medium" },
                { value: "high", label: "High" },
                { value: "urgent", label: "Urgent" },
              ]}
              className="w-40"
            />
            <Select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              options={[
                { value: "all", label: "All Sources" },
                { value: "website", label: "Website" },
                { value: "referral", label: "Referral" },
                { value: "outreach", label: "Outreach" },
                { value: "telegram", label: "Telegram" },
                { value: "other", label: "Other" },
              ]}
              className="w-40"
            />
          </div>
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">
              {search || statusFilter !== "all" || priorityFilter !== "all" || sourceFilter !== "all"
                ? "No leads match your filters"
                : "No leads yet"}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>BANT Score</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Assigned BDM</TableHead>
                  <TableHead>Last Contact</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((lead) => (
                  <TableRow
                    key={lead.id}
                    className="cursor-pointer"
                    onClick={() => setDetailLead(lead)}
                  >
                    <TableCell className="font-medium">{lead.name}</TableCell>
                    <TableCell className="text-muted-foreground">{lead.company || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={(statusVariant[lead.status] ?? "secondary") as any}>
                        {lead.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={(priorityVariant[lead.priority] ?? "secondary") as any}>
                        {lead.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${lead.bant_score ?? 0}%`,
                              backgroundColor:
                                (lead.bant_score ?? 0) >= 80
                                  ? "#10b981"
                                  : (lead.bant_score ?? 0) >= 60
                                  ? "#f59e0b"
                                  : "#ef4444",
                            }}
                          />
                        </div>
                        <span className="text-xs">{lead.bant_score ?? 0}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{lead.source}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{lead.assigned_bdm ?? "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {lead.last_contact ? formatDate(lead.last_contact) : "—"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setDetailLead(lead)
                        }}
                      >
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Lead Detail Modal */}
      <Modal open={!!detailLead} onClose={() => setDetailLead(null)} title="Lead Details">
        {detailLead && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-xs text-muted-foreground block">Name</span>
                <span className="text-sm font-medium">{detailLead.name}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Company</span>
                <span className="text-sm">{detailLead.company || "—"}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Email</span>
                <span className="text-sm">{detailLead.email || "—"}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Phone</span>
                <span className="text-sm">{detailLead.phone || "—"}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Status</span>
                <Badge variant={(statusVariant[detailLead.status] ?? "secondary") as any}>
                  {detailLead.status}
                </Badge>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Priority</span>
                <Badge variant={(priorityVariant[detailLead.priority] ?? "secondary") as any}>
                  {detailLead.priority}
                </Badge>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">BANT Score</span>
                <span className="text-sm font-bold">{detailLead.bant_score ?? 0}/100</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Source</span>
                <Badge variant="secondary">{detailLead.source}</Badge>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Assigned BDM</span>
                <span className="text-sm">{detailLead.assigned_bdm ?? "—"}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Last Contact</span>
                <span className="text-sm">
                  {detailLead.last_contact ? formatDate(detailLead.last_contact) : "—"}
                </span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Created</span>
                <span className="text-sm">{formatDate(detailLead.created_at)}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Updated</span>
                <span className="text-sm">{formatDate(detailLead.updated_at)}</span>
              </div>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block">Notes</span>
              <span className="text-sm">{detailLead.notes ?? "No notes"}</span>
            </div>
          </div>
        )}
      </Modal>

      {/* Add Lead Modal */}
      <Modal
        open={addModalOpen}
        onClose={() => {
          setAddModalOpen(false)
          resetForm()
        }}
        title="Add Lead"
      >
        <form className="space-y-4" onSubmit={handleAddLead}>
          {formError && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">
              {formError}
            </div>
          )}
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Name</label>
            <Input
              placeholder="Full name"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Company</label>
            <Input
              placeholder="Company name"
              value={formCompany}
              onChange={(e) => setFormCompany(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Email</label>
            <Input
              type="email"
              placeholder="email@example.com"
              value={formEmail}
              onChange={(e) => setFormEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Phone</label>
            <Input
              placeholder="+1 555 000 0000"
              value={formPhone}
              onChange={(e) => setFormPhone(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Source</label>
            <Select
              value={formSource}
              onChange={(e) => setFormSource(e.target.value)}
              options={[
                { value: "website", label: "Website" },
                { value: "referral", label: "Referral" },
                { value: "outreach", label: "Outreach" },
                { value: "telegram", label: "Telegram" },
                { value: "other", label: "Other" },
              ]}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Priority</label>
            <Select
              value={formPriority}
              onChange={(e) => setFormPriority(e.target.value)}
              options={[
                { value: "low", label: "Low" },
                { value: "medium", label: "Medium" },
                { value: "high", label: "High" },
                { value: "urgent", label: "Urgent" },
              ]}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Notes</label>
            <Input
              placeholder="Optional notes"
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAddModalOpen(false)
                resetForm()
              }}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Adding…
                </>
              ) : (
                "Add Lead"
              )}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
