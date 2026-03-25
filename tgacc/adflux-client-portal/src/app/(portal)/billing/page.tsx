"use client";

import React, { useState, useMemo } from "react";
import { Download, Filter, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency, formatDateTime } from "@/lib/utils";

interface Transaction {
  id: string;
  client_id: string;
  type: string;
  ad_amount: number;
  commission: number;
  crypto_amount: number;
  crypto_currency: string;
  status: string;
  notes: string;
  created_at: string;
  confirmed_at: string | null;
}

function getTypeBadge(type: string) {
  switch (type) {
    case "topup":
      return <Badge variant="success">Top Up</Badge>;
    case "spend":
      return <Badge variant="secondary">Spend</Badge>;
    case "refund":
      return <Badge className="bg-sky-600 text-white">Refund</Badge>;
    case "ban_transfer":
      return <Badge variant="warning">Ban Transfer</Badge>;
    default:
      return <Badge variant="outline">{type}</Badge>;
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge variant="success">Completed</Badge>;
    case "pending":
      return <Badge variant="warning">Pending</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function BillingPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const { data: transactions, loading, error } = useApi<Transaction[]>(
    clientId ? `/payments/transactions?client_id=${clientId}` : null
  );

  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const allTxns = transactions || [];

  const filtered = useMemo(() => {
    return allTxns.filter((txn) => {
      if (typeFilter !== "all" && txn.type !== typeFilter) return false;
      if (statusFilter !== "all" && txn.status !== statusFilter) return false;
      return true;
    });
  }, [allTxns, typeFilter, statusFilter]);

  const banTransfers = useMemo(
    () => allTxns.filter((t) => t.type === "ban_transfer"),
    [allTxns]
  );

  const exportCSV = () => {
    const headers = "Date,Type,Description,Amount,Commission,Crypto,Status\n";
    const rows = filtered
      .map(
        (t) =>
          `${t.created_at},${t.type},"${t.notes}",${t.ad_amount},${t.commission},${t.crypto_currency || ""},${t.status}`
      )
      .join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `adflux-transactions-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-lg text-red-400">Failed to load transactions</p>
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Billing & Transactions</h1>
          <p className="text-gray-400">View and manage your transaction history</p>
        </div>
        <Button variant="outline" onClick={exportCSV}>
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All Transactions</TabsTrigger>
          <TabsTrigger value="ban-transfers">Ban Transfers</TabsTrigger>
        </TabsList>

        <TabsContent value="all">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle>Transaction History</CardTitle>
                <div className="flex items-center gap-3">
                  <Select value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger className="w-[140px]">
                      <Filter className="mr-2 h-4 w-4" />
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="topup">Top Up</SelectItem>
                      <SelectItem value="spend">Spend</SelectItem>
                      <SelectItem value="refund">Refund</SelectItem>
                      <SelectItem value="ban_transfer">Ban Transfer</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[140px]">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="failed">Failed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Commission</TableHead>
                    <TableHead>Crypto</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((txn) => (
                    <TableRow key={txn.id}>
                      <TableCell className="whitespace-nowrap text-gray-300">
                        {formatDateTime(txn.created_at)}
                      </TableCell>
                      <TableCell>{getTypeBadge(txn.type)}</TableCell>
                      <TableCell className="max-w-[200px] truncate text-gray-300">
                        {txn.notes}
                      </TableCell>
                      <TableCell
                        className={`text-right ${
                          txn.ad_amount >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {txn.ad_amount >= 0 ? "+" : ""}
                        {formatCurrency(Math.abs(txn.ad_amount))}
                      </TableCell>
                      <TableCell className="text-right text-gray-400">
                        {txn.commission > 0 ? formatCurrency(txn.commission) : "—"}
                      </TableCell>
                      <TableCell>
                        {txn.crypto_currency ? (
                          <Badge variant="outline">{txn.crypto_currency.toUpperCase()}</Badge>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </TableCell>
                      <TableCell>{getStatusBadge(txn.status)}</TableCell>
                    </TableRow>
                  ))}
                  {filtered.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-gray-400">
                        No transactions found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ban-transfers">
          <Card>
            <CardHeader>
              <CardTitle>Ban Transfer History</CardTitle>
            </CardHeader>
            <CardContent>
              {banTransfers.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {banTransfers.map((txn) => (
                      <TableRow key={txn.id}>
                        <TableCell className="text-gray-300">{formatDateTime(txn.created_at)}</TableCell>
                        <TableCell className="text-gray-300">{txn.notes}</TableCell>
                        <TableCell className="text-right text-green-400">
                          +{formatCurrency(Math.abs(txn.ad_amount))}
                        </TableCell>
                        <TableCell>{getStatusBadge(txn.status)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="py-8 text-center text-gray-400">No ban transfers found.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
