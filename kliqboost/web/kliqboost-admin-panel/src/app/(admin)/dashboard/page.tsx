"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  DollarSign, Users, CreditCard, Ban, AlertTriangle, TrendingUp,
  ArrowUpRight, ArrowDownRight, Loader2, BarChart3, Bot, Brain,
  Radio, Shield, CheckCircle2, XCircle,
} from "lucide-react"
import dynamic from "next/dynamic"
const RevenueChart = dynamic(() => import("@/components/charts/revenue-chart"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      Loading chart…
    </div>
  ),
})
import { useApi } from "@/lib/api"
import { formatCurrency, formatDateTime } from "@/lib/utils"
import { FadeIn, StaggerChildren, StaggerItem, AnimatedCounter } from "@/components/motion"
import { useSession } from "next-auth/react"

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

interface SystemStatus {
  ai_brain: { status: string; model: string; endpoint: string }
  userbot_daemon: { status: string; conversations: number; hot_leads: number }
  channels: {
    main: { id: number; username: string }
    vouches: { id: number; username: string }
  }
  admins: { username: string; role: string }[]
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

interface RevenuePoint {
  date: string
  revenue: number
}

interface Deposit {
  id: string
  amount: number
  net_amount: number
  status: string
  created_at: string
  [key: string]: any
}

// ── Helpers ─────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-emerald-500/60" />
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 backdrop-blur-sm px-4 py-3 text-sm text-red-400">
      {message}
    </div>
  )
}

function getGreeting(): { text: string; emoji: string } {
  const hour = new Date().getHours()
  if (hour < 12) return { text: "Good morning", emoji: "☀️" }
  if (hour < 18) return { text: "Good afternoon", emoji: "🌤️" }
  return { text: "Good evening", emoji: "🌙" }
}

const outreachBadgeVariant: Record<string, "info" | "success" | "destructive" | "secondary"> = {
  new: "info",
  contacted: "success",
  dead: "destructive",
}

const statBorderClasses = [
  "stat-border-emerald",
  "stat-border-blue",
  "stat-border-violet",
  "stat-border-rose",
  "stat-border-amber",
  "stat-border-cyan",
]

interface BotDashboard {
  bot_users: number
  autoresponder_users: number
  leads_hot: number
  leads_warm: number
  deal_rooms_done: number
  deal_rooms_pending: number
  latest_snapshot?: {
    bot_total_messages: number
    bot_messages_today: number
    autoresponder_total: number
    recorded_at: string | null
  }
}

// ── Page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: dashboard, loading: dashLoading, error: dashError } = useApi<DashboardStats>("/admin/dashboard")
  const { data: revenue, loading: revLoading, error: revError } = useApi<RevenueStats>("/finance/revenue")
  const { data: outreach, loading: outLoading } = useApi<OutreachStats>("/outreach/sqlite/stats")
  const { data: recentTxns, loading: txnLoading } = useApi<Transaction[]>("/payments/transactions?limit=10")
  const { data: systemStatus } = useApi<SystemStatus>("/admin/system-status")
  const { data: botStats } = useApi<BotDashboard>("/bot-stats/dashboard")
  const { data: revenueTimeseries, error: tsError } = useApi<RevenuePoint[]>("/finance/revenue-timeseries?days=30")
  const { data: depositsForChart } = useApi<Deposit[]>("/finance/deposits?limit=100")

  const isLoading = dashLoading || revLoading
  const greeting = getGreeting()
  const { data: session } = useSession()
  const adminName =
    (session?.user?.name?.trim().split(/\s+/)[0]) ||
    (session?.user?.email?.split("@")[0]) ||
    "Admin"

  // Build chart data: prefer timeseries endpoint; fall back to deposit aggregation
  const chartData: RevenuePoint[] = (() => {
    if (revenueTimeseries && revenueTimeseries.length > 0) return revenueTimeseries
    if (depositsForChart && depositsForChart.length > 0) {
      const byDate: Record<string, number> = {}
      depositsForChart.forEach((d) => {
        if (d.status === "completed") {
          const day = d.created_at.slice(0, 10)
          byDate[day] = (byDate[day] ?? 0) + (d.net_amount ?? d.amount ?? 0)
        }
      })
      return Object.entries(byDate)
        .sort(([a], [b]) => a.localeCompare(b))
        .slice(-30)
        .map(([date, revenue]) => ({ date, revenue }))
    }
    return []
  })()

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">
          {greeting.emoji} {greeting.text}, <span className="text-gradient">{adminName}</span>
        </h1>
        <Spinner />
      </div>
    )
  }

  if (dashError || revError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">
          {greeting.emoji} {greeting.text}, <span className="text-gradient">{adminName}</span>
        </h1>
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
      valueGradient: "from-emerald-400 to-cyan-400",
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
      valueGradient: "from-blue-400 to-indigo-400",
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
      valueGradient: "from-violet-400 to-purple-400",
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
      valueGradient: "from-red-400 to-rose-400",
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
      valueGradient: "from-amber-400 to-yellow-400",
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
      valueGradient: "from-cyan-400 to-emerald-400",
    },
  ]

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div className="space-y-8">
      <FadeIn direction="down" distance={12}>
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="mr-2">{greeting.emoji}</span>
          {greeting.text},{" "}
          <span className="text-gradient">{adminName}</span>
        </h1>
        <p className="mt-1 text-sm text-zinc-500">Here&apos;s what&apos;s happening across your platform today.</p>
      </FadeIn>

      {/* ── System Status (Live) ──────────────────────────────── */}
      <FadeIn delay={0.05}>
        <Card className="glass-card overflow-hidden">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />
          <CardHeader className="pb-3">
            <CardTitle className="text-base section-header flex items-center gap-2">
              <Radio className="h-4 w-4 text-cyan-400 animate-pulse" />
              System Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* AI Brain */}
              <div className="glass-card rounded-xl p-4 stat-border-cyan hover:scale-[1.02] transition-transform">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/10 ring-1 ring-white/5">
                    <Brain className="h-5 w-5 text-cyan-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">AI Brain</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {systemStatus?.ai_brain.status === "online" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-red-400" />
                      )}
                      <span className={`text-xs font-semibold ${systemStatus?.ai_brain.status === "online" ? "text-emerald-400" : "text-red-400"}`}>
                        {systemStatus?.ai_brain.status ?? "checking…"}
                      </span>
                    </div>
                  </div>
                </div>
                <p className="text-[10px] text-zinc-600 font-mono truncate">{systemStatus?.ai_brain.model ?? "—"}</p>
              </div>

              {/* Userbot Daemon */}
              <div className="glass-card rounded-xl p-4 stat-border-emerald hover:scale-[1.02] transition-transform">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-white/5">
                    <Bot className="h-5 w-5 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Userbot</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {systemStatus?.userbot_daemon.status === "online" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-red-400" />
                      )}
                      <span className={`text-xs font-semibold ${systemStatus?.userbot_daemon.status === "online" ? "text-emerald-400" : "text-red-400"}`}>
                        {systemStatus?.userbot_daemon.status ?? "checking…"}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-zinc-600">
                  <span>{systemStatus?.userbot_daemon.conversations ?? 0} convos</span>
                  <span className="text-emerald-400 font-semibold">{systemStatus?.userbot_daemon.hot_leads ?? 0} hot leads</span>
                </div>
              </div>

              {/* Channels */}
              <div className="glass-card rounded-xl p-4 stat-border-blue hover:scale-[1.02] transition-transform">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 ring-1 ring-white/5">
                    <Radio className="h-5 w-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Channels</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      <span className="text-xs font-semibold text-emerald-400">2 active</span>
                    </div>
                  </div>
                </div>
                <div className="space-y-0.5 text-[10px] text-zinc-600 font-mono">
                  <p>@{systemStatus?.channels.main.username ?? "—"}</p>
                  <p>@{systemStatus?.channels.vouches.username ?? "—"}</p>
                </div>
              </div>

              {/* Team */}
              <div className="glass-card rounded-xl p-4 stat-border-violet hover:scale-[1.02] transition-transform">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 ring-1 ring-white/5">
                    <Shield className="h-5 w-5 text-violet-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Team</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      <span className="text-xs font-semibold text-emerald-400">{systemStatus?.admins?.length ?? 0} members</span>
                    </div>
                  </div>
                </div>
                <div className="space-y-0.5 text-[10px] text-zinc-600">
                  {systemStatus?.admins?.map((a) => (
                    <p key={a.username}>@{a.username} — {a.role}</p>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </FadeIn>

      {/* ── Bot Pipeline Stats ──────────────────────────────── */}
      {botStats && (
        <FadeIn delay={0.07}>
          <Card className="glass-card overflow-hidden">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />
            <CardHeader className="pb-3">
              <CardTitle className="text-base section-header flex items-center gap-2">
                <Bot className="h-4 w-4 text-emerald-400" />
                Bot Pipeline
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="glass-card rounded-xl p-3 stat-border-cyan">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Bot Users</p>
                  <p className="text-lg font-bold text-cyan-400">{botStats.bot_users}</p>
                </div>
                <div className="glass-card rounded-xl p-3 stat-border-blue">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Autoresponder</p>
                  <p className="text-lg font-bold text-blue-400">{botStats.autoresponder_users}</p>
                </div>
                <div className="glass-card rounded-xl p-3 stat-border-emerald">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">🔥 Hot Leads</p>
                  <p className="text-lg font-bold text-emerald-400">{botStats.leads_hot}</p>
                </div>
                <div className="glass-card rounded-xl p-3 stat-border-amber">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">🌡️ Warm Leads</p>
                  <p className="text-lg font-bold text-amber-400">{botStats.leads_warm}</p>
                </div>
                <div className="glass-card rounded-xl p-3 stat-border-violet">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Deal Rooms ✅</p>
                  <p className="text-lg font-bold text-violet-400">{botStats.deal_rooms_done}</p>
                </div>
                <div className="glass-card rounded-xl p-3 stat-border-rose">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Rooms Pending</p>
                  <p className="text-lg font-bold text-rose-400">{botStats.deal_rooms_pending}</p>
                </div>
              </div>
              {botStats.latest_snapshot && (
                <div className="mt-3 flex items-center gap-4 text-[10px] text-zinc-600">
                  <span>💬 {botStats.latest_snapshot.bot_total_messages} total msgs</span>
                  <span>📨 {botStats.latest_snapshot.bot_messages_today} today</span>
                  <span>🤖 {botStats.latest_snapshot.autoresponder_total} AR convos</span>
                  {botStats.latest_snapshot.recorded_at && (
                    <span className="ml-auto">Last sync: {new Date(botStats.latest_snapshot.recorded_at).toLocaleTimeString()}</span>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      )}
      <StaggerChildren className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {stats.map((stat, idx) => (
          <StaggerItem key={stat.title}>
            <Card className={`glass-card stat-card-hover hover:scale-[1.03] hover:-translate-y-1 transition-all duration-300 overflow-hidden ${statBorderClasses[idx]}`}>
              <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent" />
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{stat.title}</span>
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.iconBg} ring-1 ring-white/5`}>
                    <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
                  </div>
                </div>
                <div className={`text-2xl font-extrabold bg-gradient-to-r ${stat.valueGradient} bg-clip-text text-transparent`}>
                  <AnimatedCounter
                    value={stat.numericValue}
                    prefix={stat.isCurrency ? "$" : ""}
                    decimals={stat.isCurrency ? 2 : 0}
                    duration={1.5}
                  />
                </div>
                {stat.subtitle && (
                  <div className="flex items-center gap-1 mt-1.5">
                    {stat.trend === "up" ? (
                      <ArrowUpRight className="h-3 w-3 text-emerald-400" />
                    ) : (
                      <ArrowDownRight className="h-3 w-3 text-red-400" />
                    )}
                    <span className={`text-xs font-medium ${stat.trend === "up" ? "text-emerald-400" : "text-red-400"}`}>
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
          <Card className="glass-card h-full overflow-hidden">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />
            <CardHeader>
              <CardTitle className="text-base section-header">Revenue Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {revLoading ? (
                <Spinner />
              ) : revenue ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="glass-card rounded-xl p-4 stat-border-emerald hover:scale-[1.02] transition-transform">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Total Revenue</p>
                      <p className="text-xl font-extrabold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                        <AnimatedCounter value={revenue.total_revenue} prefix="$" decimals={2} delay={0.2} />
                      </p>
                    </div>
                    <div className="glass-card rounded-xl p-4 stat-border-blue hover:scale-[1.02] transition-transform">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-blue-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Commission Earned</p>
                      <p className="text-xl font-extrabold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                        <AnimatedCounter value={revenue.total_commission} prefix="$" decimals={2} delay={0.3} />
                      </p>
                    </div>
                    <div className="glass-card rounded-xl p-4 stat-border-violet hover:scale-[1.02] transition-transform">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-violet-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Total Ad Spend</p>
                      <p className="text-xl font-extrabold bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">
                        <AnimatedCounter value={revenue.total_ad_spend} prefix="$" decimals={2} delay={0.4} />
                      </p>
                    </div>
                    <div className="glass-card rounded-xl p-4 stat-border-cyan hover:scale-[1.02] transition-transform">
                      <div className="h-px w-full bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent mb-3" />
                      <p className="text-xs text-muted-foreground mb-1">Transactions</p>
                      <p className="text-xl font-extrabold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">
                        <AnimatedCounter value={revenue.transaction_count} delay={0.5} />
                      </p>
                    </div>
                  </div>
                  {chartData.length > 0 ? (
                    <div className="h-48 w-full">
                      <RevenueChart data={chartData} />
                    </div>
                  ) : (
                    <div className="relative flex items-center justify-center gap-2 rounded-xl border border-dashed border-emerald-500/20 bg-gradient-to-br from-emerald-500/[0.03] to-cyan-500/[0.03] py-8 text-muted-foreground overflow-hidden">
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-emerald-500/5 to-transparent" />
                      <BarChart3 className="h-5 w-5 text-emerald-500/40" />
                      <span className="text-xs font-medium text-zinc-500">No revenue data available yet</span>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No revenue data available.</p>
              )}
            </CardContent>
          </Card>
        </FadeIn>

        {/* ── Outreach Pipeline ──────────────────────────────── */}
        <FadeIn delay={0.2}>
          <Card className="glass-card h-full overflow-hidden">
            <div className="h-px w-full bg-gradient-to-r from-transparent via-blue-500/50 to-transparent" />
            <CardHeader>
              <CardTitle className="text-base section-header">Outreach Pipeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {outLoading ? (
                <Spinner />
              ) : outreach ? (
                <>
                  {Object.entries(outreach).map(([status, count]) => (
                    <div
                      key={status}
                      className="glass-card flex items-center justify-between rounded-xl p-3 hover:scale-[1.01] transition-transform"
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
                        <span className="font-semibold text-emerald-400">{conversionRate}%</span>
                      </div>
                      <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-800/80 ring-1 ring-white/5">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-cyan-500 to-emerald-400 transition-all duration-700 shadow-[0_0_12px_rgba(16,185,129,0.4)]"
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
        <Card className="glass-card overflow-hidden">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />
          <CardHeader>
            <CardTitle className="text-base section-header">Recent Transactions</CardTitle>
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
                    <TableRow key={txn.id ?? idx} className="hover:bg-emerald-500/[0.03] transition-colors">
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className={`h-2 w-2 rounded-full shrink-0 ${
                            txn.status === "failed" ? "bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.6)]" :
                            txn.status === "completed" ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" :
                            "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.6)]"
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
                      <TableCell className="text-right font-semibold">
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
    </div>
  )
}
