"use client"

import { useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Modal } from "@/components/ui/modal"
import { Select } from "@/components/ui/select"
import { Search, Plus, ExternalLink, Loader2 } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatCurrency, formatDate } from "@/lib/utils"

type ClientStatus = "active" | "suspended" | "pending" | "churned"
type ClientPlan = "starter" | "growth" | "premium" | "enterprise" | "custom"

interface Client {
  id: string
  name: string
  company: string
  tg_username: string
  tg_user_id: string | null
  email: string
  plan: ClientPlan
  status: ClientStatus
  niche: string
  monthly_spend_est: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

interface ClientStats {
  total_clients: number
  active_clients: number
  total_accounts: number
  total_spend: number
}

const statusColors: Record<ClientStatus, string> = {
  active: "success",
  suspended: "destructive",
  pending: "warning",
  churned: "secondary",
}

const planColors: Record<ClientPlan, string> = {
  starter: "secondary",
  growth: "info",
  premium: "default",
  enterprise: "warning",
  custom: "default",
}

export default function ClientsPage() {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const token = useApiToken()
  const { data: clients, loading, error, refetch } = useApi<Client[]>("/clients")
  const { data: stats } = useApi<ClientStats>("/clients/stats")

  // Form state
  const [formName, setFormName] = useState("")
  const [formCompany, setFormCompany] = useState("")
  const [formEmail, setFormEmail] = useState("")
  const [formTelegram, setFormTelegram] = useState("")
  const [formPlan, setFormPlan] = useState("starter")
  const [formNiche, setFormNiche] = useState("")

  const resetForm = () => {
    setFormName("")
    setFormCompany("")
    setFormEmail("")
    setFormTelegram("")
    setFormPlan("starter")
    setFormNiche("")
    setFormError(null)
  }

  const handleAddClient = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setFormError(null)
    try {
      await apiFetch("/clients", token, {
        method: "POST",
        body: JSON.stringify({
          name: formName,
          company: formCompany,
          email: formEmail,
          plan: formPlan,
          niche: formNiche,
          tg_username: formTelegram.replace(/^@/, ""),
          notes: "",
        }),
      })
      setAddModalOpen(false)
      resetForm()
      refetch()
    } catch (err: any) {
      setFormError(err.message || "Failed to add client")
    } finally {
      setSubmitting(false)
    }
  }

  const filtered = (clients ?? []).filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.company.toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === "all" || c.status === statusFilter
    return matchesSearch && matchesStatus
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading clients…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load clients: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Clients</h1>
        <Button onClick={() => setAddModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" /> Add Client
        </Button>
      </div>

      {/* Stats summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card><CardContent className="pt-4 pb-4"><span className="text-xs text-muted-foreground block">Total Clients</span><span className="text-xl font-bold">{stats.total_clients}</span></CardContent></Card>
          <Card><CardContent className="pt-4 pb-4"><span className="text-xs text-muted-foreground block">Active Clients</span><span className="text-xl font-bold">{stats.active_clients}</span></CardContent></Card>
          <Card><CardContent className="pt-4 pb-4"><span className="text-xs text-muted-foreground block">Total Accounts</span><span className="text-xl font-bold">{stats.total_accounts}</span></CardContent></Card>
          <Card><CardContent className="pt-4 pb-4"><span className="text-xs text-muted-foreground block">Total Spend</span><span className="text-xl font-bold">{formatCurrency(stats.total_spend)}</span></CardContent></Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search clients..."
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
                { value: "active", label: "Active" },
                { value: "suspended", label: "Suspended" },
                { value: "pending", label: "Pending" },
                { value: "churned", label: "Churned" },
              ]}
              className="w-40"
            />
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Niche</TableHead>
                <TableHead>Telegram</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    {search || statusFilter !== "all" ? "No clients match your filters" : "No clients yet"}
                  </TableCell>
                </TableRow>
              ) : filtered.map((client) => (
                <TableRow key={client.id}>
                  <TableCell className="font-medium">{client.name}</TableCell>
                  <TableCell className="text-muted-foreground">{client.company}</TableCell>
                  <TableCell>
                    <Badge variant={planColors[client.plan] as any}>{client.plan}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusColors[client.status] as any}>{client.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{client.niche}</TableCell>
                  <TableCell className="text-muted-foreground text-xs">@{client.tg_username}</TableCell>
                  <TableCell className="text-muted-foreground text-xs">{formatDate(client.created_at)}</TableCell>
                  <TableCell>
                    <Link href={`/clients/${client.id}`}>
                      <Button variant="ghost" size="icon">
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Add Client Modal */}
      <Modal open={addModalOpen} onClose={() => { setAddModalOpen(false); resetForm() }} title="Add Client">
        <form className="space-y-4" onSubmit={handleAddClient}>
          {formError && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{formError}</div>
          )}
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Name</label>
            <Input placeholder="Full name" value={formName} onChange={(e) => setFormName(e.target.value)} required />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Company</label>
            <Input placeholder="Company name" value={formCompany} onChange={(e) => setFormCompany(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Email</label>
            <Input type="email" placeholder="email@example.com" value={formEmail} onChange={(e) => setFormEmail(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Telegram</label>
            <Input placeholder="@username" value={formTelegram} onChange={(e) => setFormTelegram(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Plan</label>
            <Select
              value={formPlan}
              onChange={(e) => setFormPlan(e.target.value)}
              options={[
                { value: "starter", label: "Starter" },
                { value: "growth", label: "Growth" },
                { value: "premium", label: "Premium" },
                { value: "enterprise", label: "Enterprise" },
                { value: "custom", label: "Custom" },
              ]}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Niche</label>
            <Input placeholder="e.g. E-commerce, SaaS" value={formNiche} onChange={(e) => setFormNiche(e.target.value)} />
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => { setAddModalOpen(false); resetForm() }} className="flex-1">Cancel</Button>
            <Button type="submit" className="flex-1" disabled={submitting}>
              {submitting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Adding…</> : "Add Client"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
