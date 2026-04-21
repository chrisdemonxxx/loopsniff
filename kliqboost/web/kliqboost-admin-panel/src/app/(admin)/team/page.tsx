"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Loader2, Users, Target, TrendingUp, DollarSign } from "lucide-react"
import { useApi } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"

interface Employee {
  id: string
  name: string
  email: string
  role: string
  status: string
  created_at: string
}

interface TargetEntry {
  user_id: string
  user_name: string
  leads_target: number
  leads_actual: number
  revenue_target: number
  revenue_actual: number
  conversions_target: number
  conversions_actual: number
}

const statusVariant: Record<string, string> = {
  active: "success",
  inactive: "secondary",
  suspended: "destructive",
}

export default function TeamPage() {
  const { data: employees, loading: empLoading, error: empError, refetch: refetchEmp } = useApi<Employee[]>("/admin/users")
  const { data: targets, loading: tgtLoading, error: tgtError } = useApi<TargetEntry[]>("/crm/targets")

  const loading = empLoading || tgtLoading
  const error = empError || tgtError

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading team data…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load team data: {error}</p>
        <Button variant="outline" onClick={refetchEmp}>Retry</Button>
      </div>
    )
  }

  const empList = employees ?? []
  const tgtList = targets ?? []

  const totalLeadsTarget = tgtList.reduce((s, t) => s + (t.leads_target ?? 0), 0)
  const totalLeadsActual = tgtList.reduce((s, t) => s + (t.leads_actual ?? 0), 0)
  const totalRevenueTarget = tgtList.reduce((s, t) => s + (t.revenue_target ?? 0), 0)
  const totalRevenueActual = tgtList.reduce((s, t) => s + (t.revenue_actual ?? 0), 0)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Team Management</h1>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Team Members</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <Users className="h-4 w-4 text-blue-400" /> {empList.length}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Leads (Actual / Target)</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <Target className="h-4 w-4 text-violet-400" /> {totalLeadsActual} / {totalLeadsTarget}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Revenue (Actual / Target)</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-emerald-400" /> {formatCurrency(totalRevenueActual)}
            </span>
            <span className="text-xs text-muted-foreground">/ {formatCurrency(totalRevenueTarget)}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Lead Attainment</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-amber-400" />
              {totalLeadsTarget > 0 ? ((totalLeadsActual / totalLeadsTarget) * 100).toFixed(1) : "0.0"}%
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Employee List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Team Members</CardTitle>
        </CardHeader>
        <CardContent>
          {empList.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No team members found</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {empList.map((emp) => (
                  <TableRow key={emp.id}>
                    <TableCell className="font-medium">{emp.name}</TableCell>
                    <TableCell className="text-muted-foreground">{emp.email}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{emp.role}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={(statusVariant[emp.status] ?? "secondary") as any}>
                        {emp.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Targets Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Targets Overview</CardTitle>
        </CardHeader>
        <CardContent>
          {tgtList.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No targets data available</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member</TableHead>
                  <TableHead>Leads (Actual / Target)</TableHead>
                  <TableHead>Revenue (Actual / Target)</TableHead>
                  <TableHead>Conversions (Actual / Target)</TableHead>
                  <TableHead>Attainment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tgtList.map((t) => {
                  const attainment =
                    t.leads_target > 0 ? ((t.leads_actual / t.leads_target) * 100).toFixed(1) : "—"
                  return (
                    <TableRow key={t.user_id}>
                      <TableCell className="font-medium">{t.user_name}</TableCell>
                      <TableCell>
                        {t.leads_actual} / {t.leads_target}
                      </TableCell>
                      <TableCell>
                        {formatCurrency(t.revenue_actual)} / {formatCurrency(t.revenue_target)}
                      </TableCell>
                      <TableCell>
                        {t.conversions_actual} / {t.conversions_target}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            attainment === "—"
                              ? "secondary"
                              : parseFloat(attainment) >= 100
                              ? "success"
                              : parseFloat(attainment) >= 70
                              ? "warning"
                              : ("destructive" as any)
                          }
                        >
                          {attainment === "—" ? "—" : `${attainment}%`}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
