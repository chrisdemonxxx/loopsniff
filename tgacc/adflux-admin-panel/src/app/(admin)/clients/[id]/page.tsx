"use client"

import { use, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Modal } from "@/components/ui/modal"
import { Select } from "@/components/ui/select"
import { ArrowLeft, Edit, Ban, CreditCard, MessageSquare, Loader2, CheckCircle } from "lucide-react"
import Link from "next/link"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils"

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

interface Account {
  id: string
  client_id: string
  platform: string
  account_id: string
  name: string
  status: string
  balance: number
  spend_30d: number
  daily_limit: number
  created_at: string
}

interface Transaction {
  id: string
  client_id: string
  type: string
  ad_amount: number
  commission: number
  crypto_amount: number
  currency: string
  status: string
  date: string
  description: string
}

export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const token = useApiToken()
  const { data: client, loading, error, refetch } = useApi<Client>(`/clients/${id}`)
  const { data: clientAccounts, loading: accountsLoading } = useApi<Account[]>(`/accounts?client_id=${id}`)
  const { data: clientTransactions, loading: txLoading } = useApi<Transaction[]>(`/payments/transactions?client_id=${id}`)

  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [planModalOpen, setPlanModalOpen] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState<string>("")
  const [notesValue, setNotesValue] = useState<string | null>(null)
  const [notesSaving, setNotesSaving] = useState(false)
  const [notesSaved, setNotesSaved] = useState(false)

  const accounts = clientAccounts ?? []
  const txns = clientTransactions ?? []

  const handleSuspend = async () => {
    if (!token || !client) return
    const newStatus = client.status === "suspended" ? "active" : "suspended"
    setActionLoading("suspend")
    setActionError(null)
    try {
      await apiFetch(`/clients/${id}`, token, {
        method: "PUT",
        body: JSON.stringify({ status: newStatus }),
      })
      refetch()
    } catch (err: any) {
      setActionError(err.message || "Failed to update status")
    } finally {
      setActionLoading(null)
    }
  }

  const handleChangePlan = async () => {
    if (!token || !selectedPlan) return
    setActionLoading("plan")
    setActionError(null)
    try {
      await apiFetch(`/clients/${id}`, token, {
        method: "PUT",
        body: JSON.stringify({ plan: selectedPlan }),
      })
      setPlanModalOpen(false)
      refetch()
    } catch (err: any) {
      setActionError(err.message || "Failed to change plan")
    } finally {
      setActionLoading(null)
    }
  }

  const handleSaveNotes = async () => {
    if (!token || notesValue === null) return
    setNotesSaving(true)
    setNotesSaved(false)
    try {
      await apiFetch(`/clients/${id}`, token, {
        method: "PUT",
        body: JSON.stringify({ notes: notesValue }),
      })
      setNotesSaved(true)
      refetch()
      setTimeout(() => setNotesSaved(false), 2000)
    } catch (err: any) {
      setActionError(err.message || "Failed to save notes")
    } finally {
      setNotesSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading client…</span>
      </div>
    )
  }

  if (error || !client) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-destructive">{error || "Client not found"}</p>
        <Link href="/clients"><Button variant="outline">Back to Clients</Button></Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/clients">
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <h1 className="text-2xl font-bold">{client.name}</h1>
        <Badge variant={client.status === "active" ? "success" : "destructive"}>{client.status}</Badge>
      </div>

      {actionError && (
        <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{actionError}</div>
      )}

      {/* Client Info Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Client Information</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div><span className="text-xs text-muted-foreground block">Company</span><span className="text-sm font-medium">{client.company}</span></div>
            <div><span className="text-xs text-muted-foreground block">Email</span><span className="text-sm font-medium">{client.email}</span></div>
            <div><span className="text-xs text-muted-foreground block">Telegram</span><span className="text-sm font-medium">@{client.tg_username}</span></div>
            <div><span className="text-xs text-muted-foreground block">Plan</span><Badge variant="default">{client.plan}</Badge></div>
            <div><span className="text-xs text-muted-foreground block">Niche</span><span className="text-sm font-medium">{client.niche}</span></div>
            <div><span className="text-xs text-muted-foreground block">Est. Monthly Spend</span><span className="text-sm font-medium">{client.monthly_spend_est != null ? formatCurrency(client.monthly_spend_est) : "—"}</span></div>
            <div><span className="text-xs text-muted-foreground block">Accounts</span><span className="text-sm font-medium">{accounts.length}</span></div>
            <div><span className="text-xs text-muted-foreground block">Member Since</span><span className="text-sm font-medium">{formatDate(client.created_at)}</span></div>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button
          variant={client.status === "suspended" ? "default" : "destructive"}
          size="sm"
          onClick={handleSuspend}
          disabled={actionLoading === "suspend"}
        >
          {actionLoading === "suspend" ? <Loader2 className="h-3 w-3 mr-2 animate-spin" /> : <Ban className="h-3 w-3 mr-2" />}
          {client.status === "suspended" ? "Reactivate Client" : "Suspend Client"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => { setSelectedPlan(client.plan); setPlanModalOpen(true) }}>
          <Edit className="h-3 w-3 mr-2" /> Change Plan
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="accounts">
        <TabsList>
          <TabsTrigger value="accounts">Accounts ({accounts.length})</TabsTrigger>
          <TabsTrigger value="transactions">Transactions ({txns.length})</TabsTrigger>
          <TabsTrigger value="chat">Chat History</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="accounts">
          <Card>
            <CardContent className="pt-6">
              {accountsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground text-sm">Loading accounts…</span>
                </div>
              ) : accounts.length === 0 ? (
                <p className="text-center text-muted-foreground py-8 text-sm">No accounts found</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Account ID</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Platform</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Balance</TableHead>
                      <TableHead>Spend (30d)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {accounts.map(acc => (
                      <TableRow key={acc.id}>
                        <TableCell className="font-mono text-xs">{acc.account_id}</TableCell>
                        <TableCell>{acc.name}</TableCell>
                        <TableCell><Badge variant="secondary">{acc.platform}</Badge></TableCell>
                        <TableCell>
                          <Badge variant={acc.status === "active" ? "success" : acc.status === "banned" ? "destructive" : "warning"}>
                            {acc.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatCurrency(acc.balance)}</TableCell>
                        <TableCell>{formatCurrency(acc.spend_30d)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="transactions">
          <Card>
            <CardContent className="pt-6">
              {txLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground text-sm">Loading transactions…</span>
                </div>
              ) : txns.length === 0 ? (
                <p className="text-center text-muted-foreground py-8 text-sm">No transactions found</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Commission</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Description</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {txns.map(tx => (
                      <TableRow key={tx.id}>
                        <TableCell className="text-xs">{formatDate(tx.date)}</TableCell>
                        <TableCell><Badge variant="secondary">{tx.type}</Badge></TableCell>
                        <TableCell>{formatCurrency(tx.ad_amount)}</TableCell>
                        <TableCell>{formatCurrency(tx.commission)}</TableCell>
                        <TableCell>
                          <Badge variant={tx.status === "completed" ? "success" : tx.status === "pending" ? "warning" : "destructive"}>
                            {tx.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-xs">{tx.description}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="chat">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-muted-foreground">
                <MessageSquare className="h-4 w-4" />
                <span className="text-sm">Chat history for {client.name} — View in Bot section</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notes">
          <Card>
            <CardContent className="pt-6">
              <h3 className="text-sm font-medium mb-3">Internal Notes</h3>
              <textarea
                className="w-full h-32 rounded-md border border-border bg-secondary p-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="Add internal notes about this client..."
                value={notesValue ?? client.notes ?? ""}
                onChange={(e) => setNotesValue(e.target.value)}
              />
              <div className="flex items-center gap-2 mt-3">
                <Button size="sm" onClick={handleSaveNotes} disabled={notesSaving}>
                  {notesSaving ? <><Loader2 className="h-3 w-3 mr-2 animate-spin" /> Saving…</> : "Save Notes"}
                </Button>
                {notesSaved && (
                  <span className="text-sm text-green-500 flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" /> Saved
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Change Plan Modal */}
      <Modal open={planModalOpen} onClose={() => setPlanModalOpen(false)} title="Change Plan">
        <div className="space-y-4">
          {actionError && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{actionError}</div>
          )}
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">New Plan</label>
            <Select
              value={selectedPlan}
              onChange={(e) => setSelectedPlan(e.target.value)}
              options={[
                { value: "starter", label: "Starter" },
                { value: "growth", label: "Growth" },
                { value: "premium", label: "Premium" },
                { value: "enterprise", label: "Enterprise" },
                { value: "custom", label: "Custom" },
              ]}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => setPlanModalOpen(false)} className="flex-1">Cancel</Button>
            <Button className="flex-1" onClick={handleChangePlan} disabled={actionLoading === "plan"}>
              {actionLoading === "plan" ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving…</> : "Update Plan"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
