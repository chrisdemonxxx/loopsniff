"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  DollarSign, Users, CreditCard, Ban, AlertTriangle, TrendingUp,
  ArrowUpRight, ArrowDownRight, Loader2, BarChart3,
} from "lucide-react"
import { useApi } from "@/lib/api"
import { formatCurrency, formatDateTime } from "@/lib/utils"
import { FadeIn, StaggerChildren, StaggerItem, AnimatedCounter } from "@/components/motion"

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

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}

const outreachBadgeVariant: Record<string, "info" | "success" | "destructive" | "secondary"> = {
  new: "info",
  contacted: "success",
  dead: "destructive",
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
        <h1 className="text-2xl font-bold">{getGreeting()}, Admin</h1>
        <Spinner />
      </div>
    )
  }

  if (dashError || revError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">{getGreeting()}, Admin</h1>
        <ErrorBanner message={dashError || revError || "Failed to load dashboard data"} />
      </div>
    )
  }

  const totalLeads = outreach ? Object.values(outreach).reduce((s, v) => s + v, 0) : 0
  const conversionRate = totalLeads > 0 ? (((outreach?.contacted ?? 0) / totalLeads) * 100).toFixed(1) : "0"

  const stats = [
    {
      title: "Total Revenue",
      numericValue: dashboard?.total_revenue ?? revenue?.total_revenue ?? 0,
      isCurrency: true,
      subtitle: `${revenue?.transaction_count ?? 0} transactions`,
      icon: DollarSign,
      iconBg: "bg-emerald-500/10",
      iconColor: "text-emerald-400",
      trend: "up" as const,
    },
    {
      title: "Active Clients",
      numericValue: dashboard?.active_clients ?? 0,
      isCurrency: false,
      subtitle: `${dashboard?.total_clients ?? 0} total`,
      icon: Users,
      iconBg: "bg-blue-500/10",
      iconColor: "text-blue-400",
      trend: "up" as const,
    },
    {
      title: "Total Accounts",
      numericValue: dashboard?.total_accounts ?? 0,
      isCurrency: false,
      subtitle: `${dashboard?.active_accounts ?? 0} active`,
      icon: CreditCard,
      iconBg: "bg-violet-500/10",
      iconColor: "text-violet-400",
      trend: "up" as const,
    },
    {
      title: "Banned Accounts",
      numericValue: dashboard?.banned_accounts ?? 0,
      isCurrency: false,
      subtitle: "",
      icon: Ban,
      iconBg: "bg-red-500/10",
      iconColor: "text-red-400",
      trend: "down" as const,
    },
    {
      title: "Pending Transactions",
      numericValue: dashboard?.pending_transactions ?? 0,
      isCurrency: false,
      subtitle: "",
      icon: AlertTriangle,
      iconBg: "bg-amber-500/10",
      iconColor: "text-amber-400",
      trend: "down" as const,
    },
    {
      title: "Outreach Leads",
      numericValue: dashboard?.outreach_leads ?? totalLeads,
      isCurrency: false,
      subtitle: outLoading ? "…" : `${conversionRate}% contacted`,
      icon: TrendingUp,
      iconBg: "bg-emerald-500/10",
      iconColor: "text-emerald-400",
      trend: "up" as const,
    },
  ]

  return (
    <div className="space-y-6">
      <FadeIn direction="down" distance={12}>
        <h1 className="text-2xl font-bold">
          {getGreeting()}, <span className="text-gradient">Admin</span>
        </h1>
      </FadeIn>

      {/* ── Stat Cards ─────────────────────────────────────────── */}
      <StaggerChildren className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {stats.map((stat) => (
          <StaggerItem key={stat.title}>
            <Card className="glass-card hover:scale-[1.02] transition-all duration-300 overflow-hidden">
              <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-muted-foreground">{stat.title}</span>
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.iconBg}`}>
                    <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
                  </div>
                </div>
                <div className="text-2xl font-bold">
                  <AnimatedCounter
                    value={stat.numericValue}
                    prefix={stat.isCurrency ? "$" : ""}
                    decimals={stat.isCurrency ? 2 : 0}
                    duration={1.5}
                  />
                </div>
                {stat.subtitle && (
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
                )}
              </CardContent>
            </Card>
          </StaggerItem>
        ))}
      </StaggerChildren>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Revenue Summary ────────────────────────────────── */}
        <FadeIn delay={0.1} className="lg:col-span-2">
          <Card className="glass-card h-full">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />
            <CardHeader>
              <CardTitle className="text-base">Revenue Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {revLoading ? (
                <Spinner />
              ) : revenue ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="glass-card rounded-xl p-4">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Total Revenue</p>
                      <p className="text-xl font-bold text-emerald-400">
                        <AnimatedCounter value={revenue.total_revenue} prefix="$" decimals={2} delay={0.2} />
                      </p>
                    </div>
                    <div className="glass-card rounded-xl p-4">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-blue-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Commission Earned</p>
                      <p className="text-xl font-bold text-blue-400">
                        <AnimatedCounter value={revenue.total_commission} prefix="$" decimals={2} delay={0.3} />
                      </p>
                    </div>
                    <div className="glass-card rounded-xl p-4">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-violet-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Total Ad Spend</p>
                      <p className="text-xl font-bold text-violet-400">
                        <AnimatedCounter value={revenue.total_ad_spend} prefix="$" decimals={2} delay={0.4} />
                      </p>
                    </div>
                    <div className="glass-card rounded-xl p-4">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-zinc-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Transactions</p>
                      <p className="text-xl font-bold">
                        <AnimatedCounter value={revenue.transaction_count} delay={0.5} />
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-border/50 py-6 text-muted-foreground">
                    <BarChart3 className="h-4 w-4" />
                    <span className="text-xs">Chart coming soon</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No revenue data available.</p>
              )}
            </CardContent>
          </Card>
        </FadeIn>

        {/* ── Outreach Pipeline ──────────────────────────────── */}
        <FadeIn delay={0.2}>
          <Card className="glass-card h-full">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-blue-500/50 to-transparent" />
            <CardHeader>
              <CardTitle className="text-base">Outreach Pipeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {outLoading ? (
                <Spinner />
              ) : outreach ? (
                <>
                  {Object.entries(outreach).map(([status, count]) => (
                    <div
                      key={status}
                      className="glass-card flex items-center justify-between rounded-xl p-3"
                    >
                      <span className="text-sm font-medium capitalize">{status}</span>
                      <Badge variant={outreachBadgeVariant[status] ?? "secondary"}>
                        {count}
                      </Badge>
                    </div>
                  ))}

                  {/* Progress bar: contacted vs total */}
                  {totalLeads > 0 && (
                    <div className="pt-2 space-y-1">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Contacted</span>
                        <span>{conversionRate}%</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-700"
                          style={{ width: `${conversionRate}%` }}
                        />
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No outreach data available.</p>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      </div>

      {/* ── Recent Transactions ──────────────────────────────── */}
      <FadeIn delay={0.3}>
        <Card className="glass-card">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />
          <CardHeader>
            <CardTitle className="text-base">Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            {txnLoading ? (
              <Spinner />
            ) : recentTxns && recentTxns.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Client / Type</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentTxns.map((txn, idx) => (
                    <TableRow key={txn.id ?? idx} className="hover:bg-zinc-800/50 transition-colors">
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className={`h-2 w-2 rounded-full shrink-0 ${
                            txn.status === "failed" ? "bg-red-400" :
                            txn.status === "completed" ? "bg-emerald-400" :
                            "bg-amber-400"
                          }`} />
                          <Badge variant={
                            txn.status === "completed" ? "success" :
                            txn.status === "failed" ? "destructive" :
                            "warning"
                          }>
                            {txn.status}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>
                        {txn.client ? `${txn.client} — ` : ""}{txn.type}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatCurrency(txn.ad_amount ?? 0)}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground whitespace-nowrap">
                        {txn.created_at ? formatDateTime(txn.created_at) : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No recent transactions.</p>
            )}
          </CardContent>
        </Card>
      </FadeIn>
    </div>
  )
}
