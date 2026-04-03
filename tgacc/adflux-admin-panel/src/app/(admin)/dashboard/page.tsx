"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  DollarSign, Users, CreditCard, Ban, AlertTriangle, TrendingUp,
  ArrowUpRight, ArrowDownRight, Loader2
} from "lucide-react"
import { useApi } from "@/lib/api"
import { formatCurrency, formatDateTime } from "@/lib/utils"

// ── API response types ──────────────────────────────────────────────

interface DashboardStats {
  total_clients: number
  active_clients: number
  total_accounts: number
  active_accounts: number
  banned_accounts: number
  total_revenue: number
  pending_transactions: number
  outreach_leads: number
}

interface RevenueStats {
  total_revenue: number
  total_commission: number
  total_ad_spend: number
  transaction_count: number
}

interface OutreachStats {
  contacted: number
  dead: number
  new: number
  [key: string]: number
}

interface Transaction {
  id: string
  type: string
  ad_amount: number
  commission: number
  status: string
  created_at: string
  client?: string
  [key: string]: any
}

// ── Helpers ─────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-400">
      {message}
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: dashboard, loading: dashLoading, error: dashError } = useApi<DashboardStats>("/admin/dashboard")
  const { data: revenue, loading: revLoading, error: revError } = useApi<RevenueStats>("/finance/revenue")
  const { data: outreach, loading: outLoading } = useApi<OutreachStats>("/outreach/sqlite/stats")
  const { data: recentTxns, loading: txnLoading } = useApi<Transaction[]>("/payments/transactions?limit=10")

  const isLoading = dashLoading || revLoading

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Spinner />
      </div>
    )
  }

  if (dashError || revError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <ErrorBanner message={dashError || revError || "Failed to load dashboard data"} />
      </div>
    )
  }

  const totalLeads = outreach ? Object.values(outreach).reduce((s, v) => s + v, 0) : 0
  const conversionRate = totalLeads > 0 ? (((outreach?.contacted ?? 0) / totalLeads) * 100).toFixed(1) : "0"

  const stats = [
    {
      title: "Total Revenue",
      value: formatCurrency(dashboard?.total_revenue ?? revenue?.total_revenue ?? 0),
      subtitle: `${revenue?.transaction_count ?? 0} transactions`,
      icon: DollarSign,
      color: "text-emerald-400",
      trend: "up" as const,
    },
    {
      title: "Active Clients",
      value: `${dashboard?.active_clients ?? 0}`,
      subtitle: `${dashboard?.total_clients ?? 0} total`,
      icon: Users,
      color: "text-blue-400",
      trend: "up" as const,
    },
    {
      title: "Total Accounts",
      value: `${dashboard?.total_accounts ?? 0}`,
      subtitle: `${dashboard?.active_accounts ?? 0} active`,
      icon: CreditCard,
      color: "text-violet-400",
      trend: "up" as const,
    },
    {
      title: "Banned Accounts",
      value: `${dashboard?.banned_accounts ?? 0}`,
      subtitle: "",
      icon: Ban,
      color: "text-red-400",
      trend: "down" as const,
    },
    {
      title: "Pending Transactions",
      value: `${dashboard?.pending_transactions ?? 0}`,
      subtitle: "",
      icon: AlertTriangle,
      color: "text-amber-400",
      trend: "down" as const,
    },
    {
      title: "Outreach Leads",
      value: `${dashboard?.outreach_leads ?? totalLeads}`,
      subtitle: outLoading ? "…" : `${conversionRate}% contacted`,
      icon: TrendingUp,
      color: "text-emerald-400",
      trend: "up" as const,
    },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">{stat.title}</span>
                <stat.icon className={`h-4 w-4 ${stat.color}`} />
              </div>
              <div className="text-2xl font-bold">{stat.value}</div>
              <div className="flex items-center gap-1 mt-1">
                {stat.trend === "up" ? (
                  <ArrowUpRight className="h-3 w-3 text-emerald-400" />
                ) : (
                  <ArrowDownRight className="h-3 w-3 text-red-400" />
                )}
                <span className={`text-xs ${stat.trend === "up" ? "text-emerald-400" : "text-red-400"}`}>
                  {stat.subtitle}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Summary (API doesn't return time-series data) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Revenue Summary</CardTitle>
          </CardHeader>
          <CardContent>
            {revLoading ? (
              <Spinner />
            ) : revenue ? (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-md border border-border p-4">
                    <p className="text-xs text-muted-foreground mb-1">Total Revenue</p>
                    <p className="text-xl font-bold text-emerald-400">{formatCurrency(revenue.total_revenue)}</p>
                  </div>
                  <div className="rounded-md border border-border p-4">
                    <p className="text-xs text-muted-foreground mb-1">Commission Earned</p>
                    <p className="text-xl font-bold text-blue-400">{formatCurrency(revenue.total_commission)}</p>
                  </div>
                  <div className="rounded-md border border-border p-4">
                    <p className="text-xs text-muted-foreground mb-1">Total Ad Spend</p>
                    <p className="text-xl font-bold text-violet-400">{formatCurrency(revenue.total_ad_spend)}</p>
                  </div>
                  <div className="rounded-md border border-border p-4">
                    <p className="text-xs text-muted-foreground mb-1">Transactions</p>
                    <p className="text-xl font-bold">{revenue.transaction_count}</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground text-center">
                Revenue data visualization — coming soon
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No revenue data available.</p>
            )}
          </CardContent>
        </Card>

        {/* Outreach Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Outreach Pipeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {outLoading ? (
              <Spinner />
            ) : outreach ? (
              Object.entries(outreach).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between p-3 rounded-md border border-border bg-secondary/50">
                  <span className="text-sm font-medium capitalize">{status}</span>
                  <Badge variant="secondary">{count}</Badge>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No outreach data available.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Transactions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          {txnLoading ? (
            <Spinner />
          ) : recentTxns && recentTxns.length > 0 ? (
            <div className="space-y-3">
              {recentTxns.map((txn, idx) => (
                <div key={txn.id ?? idx} className="flex items-center gap-3 text-sm">
                  <div className={`h-2 w-2 rounded-full shrink-0 ${
                    txn.status === 'failed' ? 'bg-red-400' :
                    txn.status === 'completed' ? 'bg-emerald-400' :
                    'bg-amber-400'
                  }`} />
                  <span className="flex-1">
                    {txn.client ? `${txn.client} — ` : ""}{txn.type}{" "}
                    <span className="font-medium">{formatCurrency(txn.ad_amount ?? 0)}</span>
                  </span>
                  <Badge variant={txn.status === 'completed' ? 'secondary' : txn.status === 'failed' ? 'destructive' : 'warning'}>
                    {txn.status}
                  </Badge>
                  {txn.created_at && (
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatDateTime(txn.created_at)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No recent transactions.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
