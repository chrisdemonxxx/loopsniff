"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { DollarSign, TrendingUp, Receipt, CreditCard, ArrowRight, Loader2 } from "lucide-react"
import { useApi } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts"

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

const COLORS = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899"]

export default function FinancePage() {
  const { data: revenue, loading: revLoading, error: revError, refetch } = useApi<RevenueData>("/finance/revenue")
  const { data: ltv, loading: ltvLoading, error: ltvError } = useApi<LtvEntry[]>("/finance/ltv?limit=20")
  const { data: commission, loading: commLoading, error: commError } = useApi<CommissionEntry[]>("/finance/commission-breakdown")

  const loading = revLoading || ltvLoading || commLoading
  const error = revError || ltvError || commError

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
        <p className="text-destructive mb-2">Failed to load finance data</p>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  const revenueCards = [
    { title: "Total Revenue", value: revenue?.total_revenue ?? 0, icon: DollarSign, color: "text-emerald-400" },
    { title: "Total Commission", value: revenue?.total_commission ?? 0, icon: TrendingUp, color: "text-blue-400" },
    { title: "Total Ad Spend", value: revenue?.total_ad_spend ?? 0, icon: Receipt, color: "text-violet-400" },
    { title: "Transactions", value: revenue?.transaction_count ?? 0, icon: CreditCard, color: "text-amber-400", isCurrency: false },
  ]

  const pieData = (commission ?? []).map((c) => ({
    name: `${c.plan} (${(c.avg_rate * 100).toFixed(0)}%)`,
    value: c.total_commission,
  }))

  const clientList = ltv ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Finance</h1>
        <Link href="/finance/transactions">
          <Button variant="outline" size="sm">
            All Transactions <ArrowRight className="h-3 w-3 ml-2" />
          </Button>
        </Link>
      </div>

      {/* Revenue Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {revenueCards.map((card) => (
          <Card key={card.title}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">{card.title}</span>
                <card.icon className={`h-4 w-4 ${card.color}`} />
              </div>
              <div className="text-2xl font-bold">
                {card.isCurrency === false ? card.value.toLocaleString() : formatCurrency(card.value)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Summary */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Revenue Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
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
                <div className="text-2xl font-bold text-amber-400">{(revenue?.transaction_count ?? 0).toLocaleString()}</div>
                <div className="text-xs text-muted-foreground mt-1">Total Transactions</div>
              </div>
            </div>
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
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }} />
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

      {/* Top Clients */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Top Clients by Revenue</CardTitle>
        </CardHeader>
        <CardContent>
          {clientList.length === 0 ? (
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
              {clientList.map((cr) => (
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
    </div>
  )
}
