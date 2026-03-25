"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { Search, Download, Loader2 } from "lucide-react"
import { useApi } from "@/lib/api"
import { formatCurrency, formatDate } from "@/lib/utils"

type Transaction = {
  id: string
  client_id: string
  type: string
  ad_amount: number
  commission: number
  crypto_amount: number
  crypto_currency: string
  status: string
  notes: string | null
  created_at: string
}

export default function TransactionsPage() {
  const { data: transactions, loading, error, refetch } = useApi<Transaction[]>("/payments/transactions")
  const [search, setSearch] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null)

  const list = transactions ?? []

  const filtered = list.filter(t => {
    const matchesSearch = t.client_id.toLowerCase().includes(search.toLowerCase()) ||
      (t.notes ?? "").toLowerCase().includes(search.toLowerCase())
    const matchesType = typeFilter === "all" || t.type === typeFilter
    const matchesStatus = statusFilter === "all" || t.status === statusFilter
    return matchesSearch && matchesType && matchesStatus
  })

  const exportCSV = () => {
    const headers = "Date,Client,Type,Ad Amount,Commission,Crypto,Currency,Status,Notes\n"
    const rows = filtered.map(t =>
      `${formatDate(t.created_at)},${t.client_id},${t.type},${t.ad_amount},${t.commission},${t.crypto_amount},${t.crypto_currency},${t.status},"${t.notes ?? ""}"`
    ).join("\n")
    const blob = new Blob([headers + rows], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "transactions.csv"
    a.click()
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
        <p className="text-destructive mb-2">Failed to load transactions</p>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">All Transactions</h1>
        <Button variant="outline" size="sm" onClick={exportCSV}>
          <Download className="h-3 w-3 mr-2" /> Export CSV
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search transactions..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
            </div>
            <Select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              options={[
                { value: "all", label: "All Types" },
                { value: "deposit", label: "Deposit" },
                { value: "commission", label: "Commission" },
                { value: "setup_fee", label: "Setup Fee" },
                { value: "monthly_fee", label: "Monthly Fee" },
                { value: "refund", label: "Refund" },
                { value: "transfer", label: "Transfer" },
              ]}
              className="w-40"
            />
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "all", label: "All Statuses" },
                { value: "completed", label: "Completed" },
                { value: "pending", label: "Pending" },
                { value: "failed", label: "Failed" },
              ]}
              className="w-40"
            />
          </div>
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No transactions found</p>
          ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Ad Amount</TableHead>
                <TableHead>Commission</TableHead>
                <TableHead>Crypto</TableHead>
                <TableHead>Currency</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((tx) => (
                <TableRow key={tx.id} className="cursor-pointer" onClick={() => setSelectedTx(tx)}>
                  <TableCell className="text-xs">{formatDate(tx.created_at)}</TableCell>
                  <TableCell className="font-medium">{tx.client_id}</TableCell>
                  <TableCell><Badge variant="secondary">{tx.type.replace('_', ' ')}</Badge></TableCell>
                  <TableCell>{formatCurrency(tx.ad_amount)}</TableCell>
                  <TableCell className="text-emerald-400">{formatCurrency(tx.commission)}</TableCell>
                  <TableCell className="font-mono text-xs">{tx.crypto_amount}</TableCell>
                  <TableCell><Badge variant="info">{tx.crypto_currency}</Badge></TableCell>
                  <TableCell>
                    <Badge variant={tx.status === 'completed' ? 'success' : tx.status === 'pending' ? 'warning' : 'destructive'}>
                      {tx.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          )}
        </CardContent>
      </Card>

      {/* Transaction Detail Modal */}
      <Modal open={!!selectedTx} onClose={() => setSelectedTx(null)} title="Transaction Detail">
        {selectedTx && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><span className="text-xs text-muted-foreground block">Client</span><span className="text-sm font-medium">{selectedTx.client_id}</span></div>
              <div><span className="text-xs text-muted-foreground block">Date</span><span className="text-sm">{formatDate(selectedTx.created_at)}</span></div>
              <div><span className="text-xs text-muted-foreground block">Type</span><Badge variant="secondary">{selectedTx.type}</Badge></div>
              <div><span className="text-xs text-muted-foreground block">Status</span>
                <Badge variant={selectedTx.status === 'completed' ? 'success' : selectedTx.status === 'pending' ? 'warning' : 'destructive'}>{selectedTx.status}</Badge>
              </div>
              <div><span className="text-xs text-muted-foreground block">Ad Amount</span><span className="text-sm font-bold">{formatCurrency(selectedTx.ad_amount)}</span></div>
              <div><span className="text-xs text-muted-foreground block">Commission</span><span className="text-sm font-bold text-emerald-400">{formatCurrency(selectedTx.commission)}</span></div>
              <div><span className="text-xs text-muted-foreground block">Crypto Amount</span><span className="text-sm font-mono">{selectedTx.crypto_amount} {selectedTx.crypto_currency}</span></div>
            </div>
            <div><span className="text-xs text-muted-foreground block">Notes</span><span className="text-sm">{selectedTx.notes ?? "No notes"}</span></div>
          </div>
        )}
      </Modal>
    </div>
  )
}
