"use client"

import { useState } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  DollarSign, TrendingUp, Receipt, CreditCard, ArrowRight,
  Loader2, AlertTriangle, CheckCircle, XCircle, Search,
} from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { useToast } from "@/components/ui/toast"
import { formatCurrency, formatDateTime } from "@/lib/utils"
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts"

// ── Types ──

type RevenueData = {
  total_revenue: number
  total_commission: number
  total_ad_spend: number
  transaction_count: number
}

type LtvEntry = {
  client_id: string
  client_name: string
  total_spend: number
  total_commission: number
  transaction_count: number
  avg_transaction: number
}

type CommissionEntry = {
  plan: string
  total_commission: number
  transaction_count: number
  avg_rate: number
}

type FinanceSummary = {
  total_deposits: number
  completed_deposits: number
  pending_deposits: number
  failed_deposits: number
  total_revenue: number
  active_subscriptions: number
  subscription_mrr: number
  total_adjustments: number
}

type Deposit = {
  id: string
  wallet_id: string
  client_id: string
  client_name: string
  type: string
  amount: number
  fee: number
  net_amount: number
  currency: string
  payment_method: string | null
  payment_reference: string | null
  status: string
  notes: string | null
  created_at: string
  completed_at: string | null
}

type RevenueBreakdown = {
  source: string
  amount: number
  count: number
}

type LowBalanceAlert = {
  client_id: string
  client_name: string
  wallet_balance: number
  currency: string
}

const COLORS = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899"]

export default function FinancePage() {
  const token = useApiToken()
  const { toast } = useToast()
  const { data: summary, loading: sumLoading } = useApi<FinanceSummary>("/finance/summary")
  const { data: revenue, loading: revLoading } = useApi<RevenueData>("/finance/revenue")
  const { data: deposits, loading: depLoading, refetch: refetchDeposits } = useApi<Deposit[]>("/finance/deposits")
  const { data: breakdown, loading: brkLoading } = useApi<RevenueBreakdown[]>("/finance/revenue/breakdown")
  const { data: alerts, loading: alertLoading } = useApi<LowBalanceAlert[]>("/finance/alerts?threshold=50")
  const { data: ltv, loading: ltvLoading } = useApi<LtvEntry[]>("/finance/ltv?limit=20")
  const { data: commission, loading: commLoading } = useApi<CommissionEntry[]>("/finance/commission-breakdown")

  const loading = sumLoading || revLoading || depLoading || brkLoading || alertLoading || ltvLoading || commLoading

  // Deposits state
  const [depSearch, setDepSearch] = useState("")
  const [depStatus, setDepStatus] = useState("all")
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [actionLoading, setActionLoading] = useState(false)

  const filteredDeposits = (deposits ?? []).filter((d) => {
    const matchSearch =
      d.client_name.toLowerCase().includes(depSearch.toLowerCase()) ||
      (d.payment_reference ?? "").toLowerCase().includes(depSearch.toLowerCase())
    const matchStatus = depStatus === "all" || d.status === depStatus
    return matchSearch && matchStatus
  })

  const handleApprove = async (id: string) => {
    if (!token) return
    setActionLoading(true)
    try {
      await apiFetch(`/finance/deposits/${id}/approve`, token, { method: "PUT" })
      refetchDeposits()
    } catch (e: any) {
      toast(e.message, "error")
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!token || !rejectId || !rejectReason.trim()) return
    setActionLoading(true)
    try {
      await apiFetch(`/finance/deposits/${rejectId}/reject`, token, {
        method: "PUT",
        body: JSON.stringify({ reason: rejectReason }),
      })
      setRejectId(null)
      setRejectReason("")
      refetchDeposits()
    } catch (e: any) {
      toast(e.message, "error")
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

  // Summary cards data
  const summaryCards = [
    { title: "Total Deposits", value: formatCurrency(summary?.total_deposits ?? 0), icon: DollarSign, color: "text-emerald-400" },
    { title: "Total Revenue", value: formatCurrency(summary?.total_revenue ?? 0), icon: TrendingUp, color: "text-blue-400" },
    { title: "Pending Deposits", value: String(summary?.pending_deposits ?? 0), icon: Receipt, color: "text-amber-400" },
    { title: "Active Subscriptions", value: String(summary?.active_subscriptions ?? 0), icon: CreditCard, color: "text-violet-400" },
  ]

  // Revenue breakdown chart data
  const barData = (breakdown ?? []).map((b) => ({
    name: b.source.charAt(0).toUpperCase() + b.source.slice(1),
    amount: Number(b.amount),
    count: b.count,
  }))

  // Commission pie data
  const pieData = (commission ?? []).map((c) => ({
    name: `${c.plan} (${(c.avg_rate * 100).toFixed(0)}%)`,
    value: c.total_commission,
  }))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Finance Operations</h1>
        <Link href="/finance/transactions">
          <Button variant="outline" size="sm">
            All Transactions <ArrowRight className="h-3 w-3 ml-2" />
          </Button>
        </Link>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {summaryCards.map((card) => (
          <Card key={card.title}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">{card.title}</span>
                <card.icon className={`h-4 w-4 ${card.color}`} />
              </div>
              <div className="text-2xl font-bold">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="deposits">
        <TabsList>
          <TabsTrigger value="deposits">Deposits</TabsTrigger>
          <TabsTrigger value="revenue">Revenue</TabsTrigger>
          <TabsTrigger value="alerts">
            Alerts{(alerts?.length ?? 0) > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-amber-500/20 px-1.5 text-[10px] text-amber-400">
                {alerts?.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="clients">Top Clients</TabsTrigger>
        </TabsList>

        {/* ── Deposits Tab ── */}
        <TabsContent value="deposits">
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by client or reference..."
                    value={depSearch}
                    onChange={(e) => setDepSearch(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Select
                  value={depStatus}
                  onChange={(e) => setDepStatus(e.target.value)}
                  options={[
                    { value: "all", label: "All Statuses" },
                    { value: "pending", label: "Pending" },
                    { value: "completed", label: "Completed" },
                    { value: "failed", label: "Failed" },
                    { value: "cancelled", label: "Cancelled" },
                  ]}
                  className="w-40"
                />
              </div>
            </CardHeader>
            <CardContent>
              {filteredDeposits.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No deposits found</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Client</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Fee</TableHead>
                      <TableHead>Net</TableHead>
                      <TableHead>Method</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDeposits.map((dep) => (
                      <TableRow key={dep.id}>
                        <TableCell className="text-xs">{formatDateTime(dep.created_at)}</TableCell>
                        <TableCell className="font-medium">{dep.client_name}</TableCell>
                        <TableCell>{formatCurrency(dep.amount)}</TableCell>
                        <TableCell className="text-muted-foreground">{formatCurrency(dep.fee)}</TableCell>
                        <TableCell className="font-bold">{formatCurrency(dep.net_amount)}</TableCell>
                        <TableCell>
                          <Badge variant="info">{dep.payment_method ?? "—"}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              dep.status === "completed" ? "success" :
                              dep.status === "pending" ? "warning" : "destructive"
                            }
                          >
                            {dep.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {dep.status === "pending" && (
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleApprove(dep.id)}
                                disabled={actionLoading}
                                className="text-emerald-400 hover:text-emerald-300 h-7 px-2"
                              >
                                <CheckCircle className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setRejectId(dep.id)}
                                disabled={actionLoading}
                                className="text-red-400 hover:text-red-300 h-7 px-2"
                              >
                                <XCircle className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Revenue Tab ── */}
        <TabsContent value="revenue">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Revenue Breakdown Bar Chart */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Revenue by Source</CardTitle>
              </CardHeader>
              <CardContent>
                {barData.length === 0 ? (
                  <p className="text-center py-8 text-muted-foreground">No revenue data yet</p>
                ) : (
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                        <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "8px", color: "#f8fafc" }}
                          formatter={(value) => formatCurrency(Number(value))}
                        />
                        <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Commission Pie Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Commission Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                {pieData.length === 0 ? (
                  <p className="text-center py-8 text-muted-foreground">No commission data yet</p>
                ) : (
                  <>
                    <div className="h-[250px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                            {pieData.map((_, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "8px", color: "#f8fafc" }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="space-y-2 mt-2">
                      {pieData.map((item, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <div className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                          <span className="text-muted-foreground">{item.name}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Revenue Summary Grid */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-base">Revenue Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-secondary/50 text-center">
                  <div className="text-2xl font-bold text-emerald-400">{formatCurrency(revenue?.total_revenue ?? 0)}</div>
                  <div className="text-xs text-muted-foreground mt-1">Total Revenue</div>
                </div>
                <div className="p-4 rounded-lg bg-secondary/50 text-center">
                  <div className="text-2xl font-bold text-blue-400">{formatCurrency(revenue?.total_commission ?? 0)}</div>
                  <div className="text-xs text-muted-foreground mt-1">Total Commission</div>
                </div>
                <div className="p-4 rounded-lg bg-secondary/50 text-center">
                  <div className="text-2xl font-bold text-violet-400">{formatCurrency(revenue?.total_ad_spend ?? 0)}</div>
                  <div className="text-xs text-muted-foreground mt-1">Total Ad Spend</div>
                </div>
                <div className="p-4 rounded-lg bg-secondary/50 text-center">
                  <div className="text-2xl font-bold text-amber-400">{formatCurrency(summary?.subscription_mrr ?? 0)}</div>
                  <div className="text-xs text-muted-foreground mt-1">Subscription MRR</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Alerts Tab ── */}
        <TabsContent value="alerts">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                Low Balance Alerts
              </CardTitle>
            </CardHeader>
            <CardContent>
              {(alerts ?? []).length === 0 ? (
                <div className="text-center py-8">
                  <CheckCircle className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
                  <p className="text-muted-foreground">All client balances are healthy</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Client</TableHead>
                      <TableHead>Balance</TableHead>
                      <TableHead>Currency</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(alerts ?? []).map((a) => (
                      <TableRow key={a.client_id}>
                        <TableCell className="font-medium">{a.client_name}</TableCell>
                        <TableCell className="font-bold text-red-400">{formatCurrency(a.wallet_balance)}</TableCell>
                        <TableCell>{a.currency}</TableCell>
                        <TableCell>
                          <Badge variant={a.wallet_balance <= 0 ? "destructive" : "warning"}>
                            {a.wallet_balance <= 0 ? "Empty" : "Low"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Top Clients Tab ── */}
        <TabsContent value="clients">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Top Clients by Revenue</CardTitle>
            </CardHeader>
            <CardContent>
              {(ltv ?? []).length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No client data yet</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Client</TableHead>
                      <TableHead>Total Spend</TableHead>
                      <TableHead>Commission</TableHead>
                      <TableHead>Transactions</TableHead>
                      <TableHead>Avg Transaction</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(ltv ?? []).map((cr) => (
                      <TableRow key={cr.client_id}>
                        <TableCell className="font-medium">{cr.client_name || cr.client_id}</TableCell>
                        <TableCell>{formatCurrency(cr.total_spend)}</TableCell>
                        <TableCell className="font-bold text-emerald-400">{formatCurrency(cr.total_commission)}</TableCell>
                        <TableCell>{cr.transaction_count}</TableCell>
                        <TableCell>{formatCurrency(cr.avg_transaction)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Reject Modal */}
      <Modal open={!!rejectId} onClose={() => { setRejectId(null); setRejectReason("") }} title="Reject Deposit">
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">Provide a reason for rejecting this deposit.</p>
          <Input
            placeholder="Rejection reason..."
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => { setRejectId(null); setRejectReason("") }}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleReject}
              disabled={!rejectReason.trim() || actionLoading}
            >
              {actionLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
              Reject Deposit
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
