"use client"

import { use, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ArrowLeft, Ban, ArrowRightLeft, Plus, Minus, Loader2 } from "lucide-react"
import Link from "next/link"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatCurrency, formatDate } from "@/lib/utils"

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

export default function AccountDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data: account, loading, error, refetch } = useApi<Account>(`/accounts/${id}`)
  const token = useApiToken()
  const [balanceAmount, setBalanceAmount] = useState("")
  const [transferTarget, setTransferTarget] = useState("")
  const [transferAmount, setTransferAmount] = useState("")
  const [actionLoading, setActionLoading] = useState(false)

  const handleBalanceChange = async (direction: "add" | "subtract") => {
    if (!token || !account || !balanceAmount) return
    const amt = parseFloat(balanceAmount)
    if (isNaN(amt) || amt <= 0) return
    setActionLoading(true)
    try {
      const newBalance = direction === "add" ? account.balance + amt : account.balance - amt
      await apiFetch(`/accounts/${id}`, token, {
        method: "PUT",
        body: JSON.stringify({ balance: newBalance }),
      })
      setBalanceAmount("")
      refetch()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleBan = async () => {
    if (!token) return
    setActionLoading(true)
    try {
      await apiFetch(`/accounts/${id}/ban`, token, {
        method: "POST",
        body: JSON.stringify({ reason: "Banned via admin panel" }),
      })
      refetch()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleTransfer = async () => {
    if (!token || !transferTarget || !transferAmount) return
    const amt = parseFloat(transferAmount)
    if (isNaN(amt) || amt <= 0) return
    setActionLoading(true)
    try {
      await apiFetch(`/accounts/${id}/transfer`, token, {
        method: "POST",
        body: JSON.stringify({ new_account_id: transferTarget, amount: amt }),
      })
      setTransferTarget("")
      setTransferAmount("")
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

  if (error || !account) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive mb-2">{error ?? "Account not found"}</p>
        <Link href="/accounts"><Button variant="outline" size="sm">Back to Accounts</Button></Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/accounts">
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <h1 className="text-2xl font-bold">{account.name}</h1>
        <Badge variant={account.status === 'active' ? 'success' : account.status === 'banned' ? 'destructive' : 'warning'}>
          {account.status}
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Account Info */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Account Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div><span className="text-xs text-muted-foreground block">Account ID</span><span className="text-sm font-mono">{account.account_id}</span></div>
            <div><span className="text-xs text-muted-foreground block">Client</span><span className="text-sm">{account.client_id}</span></div>
            <div><span className="text-xs text-muted-foreground block">Platform</span><Badge variant="secondary">{account.platform}</Badge></div>
            <div><span className="text-xs text-muted-foreground block">Balance</span><span className="text-sm font-bold text-emerald-400">{formatCurrency(account.balance)}</span></div>
            <div><span className="text-xs text-muted-foreground block">Daily Limit</span><span className="text-sm">{formatCurrency(account.daily_limit)}</span></div>
            <div><span className="text-xs text-muted-foreground block">Total Spend</span><span className="text-sm">{formatCurrency(account.total_spend)}</span></div>
            <div><span className="text-xs text-muted-foreground block">Created</span><span className="text-sm">{formatDate(account.created_at)}</span></div>
            {account.banned_at && (
              <div><span className="text-xs text-muted-foreground block">Banned At</span><span className="text-sm text-destructive">{formatDate(account.banned_at)}</span></div>
            )}
            {account.ban_reason && (
              <div><span className="text-xs text-muted-foreground block">Ban Reason</span><span className="text-sm text-destructive">{account.ban_reason}</span></div>
            )}
          </CardContent>
        </Card>

        {/* Spending Summary */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Spending Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-secondary/50 text-center">
                <div className="text-2xl font-bold text-emerald-400">{formatCurrency(account.balance)}</div>
                <div className="text-xs text-muted-foreground mt-1">Current Balance</div>
              </div>
              <div className="p-4 rounded-lg bg-secondary/50 text-center">
                <div className="text-2xl font-bold text-blue-400">{formatCurrency(account.total_spend)}</div>
                <div className="text-xs text-muted-foreground mt-1">Total Spend</div>
              </div>
              <div className="p-4 rounded-lg bg-secondary/50 text-center">
                <div className="text-2xl font-bold">{formatCurrency(account.daily_limit)}</div>
                <div className="text-xs text-muted-foreground mt-1">Daily Limit</div>
              </div>
              <div className="p-4 rounded-lg bg-secondary/50 text-center">
                <div className="text-2xl font-bold">{formatDate(account.updated_at)}</div>
                <div className="text-xs text-muted-foreground mt-1">Last Updated</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Balance Management */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Balance Management</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                placeholder="Amount"
                className="w-32"
                value={balanceAmount}
                onChange={(e) => setBalanceAmount(e.target.value)}
              />
              <Button size="sm" disabled={actionLoading} onClick={() => handleBalanceChange("add")}>
                <Plus className="h-3 w-3 mr-1" /> Add
              </Button>
              <Button variant="outline" size="sm" disabled={actionLoading} onClick={() => handleBalanceChange("subtract")}>
                <Minus className="h-3 w-3 mr-1" /> Subtract
              </Button>
            </div>
            <div className="flex gap-2 ml-auto">
              <Button variant="destructive" size="sm" disabled={actionLoading} onClick={handleBan}>
                <Ban className="h-3 w-3 mr-2" /> Mark Banned
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Transfer Funds */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transfer Funds</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              placeholder="Target Account ID"
              className="w-48"
              value={transferTarget}
              onChange={(e) => setTransferTarget(e.target.value)}
            />
            <Input
              type="number"
              placeholder="Amount"
              className="w-32"
              value={transferAmount}
              onChange={(e) => setTransferAmount(e.target.value)}
            />
            <Button variant="outline" size="sm" disabled={actionLoading} onClick={handleTransfer}>
              <ArrowRightLeft className="h-3 w-3 mr-2" /> Transfer
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
