"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Loader2, Settings2 } from "lucide-react"
import { useApi } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"

interface DepositConfig {
  id: string
  method: string
  currency: string
  enabled: boolean
  min_amount: number
  max_amount: number
  fee_percent: number
  fee_fixed: number
  processing_time: string
  notes: string | null
}

export default function DepositConfigPage() {
  const { data: configs, loading, error, refetch } = useApi<DepositConfig[]>("/admin/deposit-config")

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading deposit configuration…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load deposit config: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  const configList = configs ?? []
  const enabledCount = configList.filter((c) => c.enabled).length

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <Settings2 className="h-6 w-6" /> Deposit Configuration
      </h1>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Total Methods</span>
            <span className="text-xl font-bold">{configList.length}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Enabled</span>
            <span className="text-xl font-bold text-emerald-400">{enabledCount}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Disabled</span>
            <span className="text-xl font-bold text-red-400">{configList.length - enabledCount}</span>
          </CardContent>
        </Card>
      </div>

      {/* Payment Methods Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payment Method Settings</CardTitle>
        </CardHeader>
        <CardContent>
          {configList.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No deposit methods configured</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Method</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Min Amount</TableHead>
                  <TableHead>Max Amount</TableHead>
                  <TableHead>Fee (%)</TableHead>
                  <TableHead>Fee (Fixed)</TableHead>
                  <TableHead>Processing Time</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {configList.map((config) => (
                  <TableRow key={config.id}>
                    <TableCell className="font-medium">{config.method}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{config.currency}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={config.enabled ? "success" : "destructive"}>
                        {config.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatCurrency(config.min_amount)}</TableCell>
                    <TableCell>{formatCurrency(config.max_amount)}</TableCell>
                    <TableCell>{config.fee_percent}%</TableCell>
                    <TableCell>{formatCurrency(config.fee_fixed)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {config.processing_time}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[150px] truncate">
                      {config.notes ?? "—"}
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
