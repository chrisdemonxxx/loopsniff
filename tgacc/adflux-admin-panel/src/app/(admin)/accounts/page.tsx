"use client"

import { useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { Search, ExternalLink, Ban, ArrowRightLeft, Loader2 } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { useToast } from "@/components/ui/toast"
import { formatCurrency } from "@/lib/utils"

type Account = {
  id: string
  client_id: string
  platform: string
  account_id: string
  name: string
  status: string
  balance: number
  total_spend: number
  daily_limit: number
  created_at: string
  banned_at: string | null
  ban_reason: string | null
  updated_at: string
}

const statusVariant: Record<string, string> = {
  active: "success",
  banned: "destructive",
  limited: "warning",
  pending: "info",
  disabled: "secondary",
}

export default function AccountsPage() {
  const { data: accounts, loading, error, refetch } = useApi<Account[]>("/accounts")
  const token = useApiToken()
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [platformFilter, setPlatformFilter] = useState("all")
  const [selected, setSelected] = useState<string[]>([])
  const [actionLoading, setActionLoading] = useState(false)

  // Transfer Funds
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferRecipient, setTransferRecipient] = useState("")
  const [transferAmount, setTransferAmount] = useState("")
  const [transferring, setTransferring] = useState(false)

  const { toast } = useToast()

  const handleTransfer = async () => {
    if (!token || selected.length === 0 || !transferRecipient.trim() || !transferAmount) return
    setTransferring(true)
    try {
      await apiFetch("/wallet/transfer", token, {
        method: "POST",
        body: JSON.stringify({
          from_account_ids: selected,
          to_account_id: transferRecipient,
          amount: parseFloat(transferAmount),
        }),
      })
      toast("Funds transferred successfully", "success")
      setTransferOpen(false)
      setTransferRecipient("")
      setTransferAmount("")
      setSelected([])
      refetch()
    } catch (e: any) {
      toast(e.message || "Transfer failed", "error")
    } finally {
      setTransferring(false)
    }
  }

  const list = accounts ?? []

  const filtered = list.filter(a => {
    const matchesSearch = a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.account_id.toLowerCase().includes(search.toLowerCase()) ||
      a.client_id.toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === "all" || a.status === statusFilter
    const matchesPlatform = platformFilter === "all" || a.platform === platformFilter
    return matchesSearch && matchesStatus && matchesPlatform
  })

  const toggleSelect = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id])
  }

  const handleBanSelected = async () => {
    if (!token || selected.length === 0) return
    setActionLoading(true)
    try {
      await Promise.all(selected.map(id =>
        apiFetch(`/accounts/${id}/ban`, token, { method: "POST", body: JSON.stringify({ reason: "Banned via admin panel" }) })
      ))
      setSelected([])
      refetch()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(false)
    }
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
        <p className="text-destructive mb-2">Failed to load accounts</p>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Transfer Funds Modal */}
      <Modal open={transferOpen} onClose={() => setTransferOpen(false)} title="Transfer Funds">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
              From Accounts ({selected.length} selected)
            </label>
            <div className="flex flex-wrap gap-1">
              {selected.map(id => {
                const acct = list.find(a => a.id === id)
                return (
                  <Badge key={id} variant="secondary" className="text-xs">
                    {acct?.name || id}
                  </Badge>
                )
              })}
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Recipient Account ID</label>
            <Input placeholder="Enter recipient account ID" value={transferRecipient} onChange={(e) => setTransferRecipient(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Amount</label>
            <Input type="number" placeholder="0.00" min="0" step="0.01" value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setTransferOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleTransfer} disabled={transferring || !transferRecipient.trim() || !transferAmount}>
              {transferring && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
              Transfer
            </Button>
          </div>
        </div>
      </Modal>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Ad Accounts</h1>
        {selected.length > 0 && (
          <div className="flex gap-2">
            <Button variant="destructive" size="sm" disabled={actionLoading} onClick={handleBanSelected}>
              <Ban className="h-3 w-3 mr-2" /> Mark Banned ({selected.length})
            </Button>
            <Button variant="outline" size="sm" onClick={() => setTransferOpen(true)}>
              <ArrowRightLeft className="h-3 w-3 mr-2" /> Transfer Funds
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search accounts..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
            </div>
            <Select
              value={platformFilter}
              onChange={(e) => setPlatformFilter(e.target.value)}
              options={[
                { value: "all", label: "All Platforms" },
                { value: "facebook", label: "Facebook" },
                { value: "google", label: "Google" },
                { value: "tiktok", label: "TikTok" },
                { value: "snapchat", label: "Snapchat" },
              ]}
              className="w-40"
            />
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "all", label: "All Statuses" },
                { value: "active", label: "Active" },
                { value: "banned", label: "Banned" },
                { value: "limited", label: "Limited" },
                { value: "pending", label: "Pending" },
                { value: "disabled", label: "Disabled" },
              ]}
              className="w-40"
            />
          </div>
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No accounts found</p>
          ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <input type="checkbox" className="rounded border-border" onChange={(e) => {
                    if (e.target.checked) setSelected(filtered.map(a => a.id))
                    else setSelected([])
                  }} />
                </TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Balance</TableHead>
                <TableHead>Total Spend</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((account) => (
                <TableRow key={account.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selected.includes(account.id)}
                      onChange={() => toggleSelect(account.id)}
                      className="rounded border-border"
                    />
                  </TableCell>
                  <TableCell>
                    <div>
                      <span className="font-medium">{account.name}</span>
                      <span className="block text-xs text-muted-foreground font-mono">{account.account_id}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{account.client_id}</TableCell>
                  <TableCell><Badge variant="secondary">{account.platform}</Badge></TableCell>
                  <TableCell>
                    <Badge variant={(statusVariant[account.status] ?? "secondary") as any}>{account.status}</Badge>
                  </TableCell>
                  <TableCell>{formatCurrency(account.balance)}</TableCell>
                  <TableCell>{formatCurrency(account.total_spend)}</TableCell>
                  <TableCell>
                    <Link href={`/accounts/${account.id}`}>
                      <Button variant="ghost" size="icon"><ExternalLink className="h-4 w-4" /></Button>
                    </Link>
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
