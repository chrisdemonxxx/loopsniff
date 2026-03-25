"use client";

import React, { useState, useMemo } from "react";
import { Download, TrendingUp, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApi } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface Account {
  id: string;
  platform: string;
  name: string;
  status: string;
  balance: number;
  total_spend: number;
  daily_limit: number;
}

interface Transaction {
  id: string;
  type: string;
  ad_amount: number;
  commission: number;
  crypto_currency: string;
  status: string;
  notes: string;
  created_at: string;
}

const ranges = [
  { label: "7 Days", value: 7 },
  { label: "30 Days", value: 30 },
  { label: "90 Days", value: 90 },
];

export default function SpendingPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;

  const { data: transactions, loading: txnLoading } = useApi<Transaction[]>(
    clientId ? `/payments/transactions?client_id=${clientId}` : null
  );
  const { data: accounts, loading: acctLoading } = useApi<Account[]>(
    clientId ? `/accounts?client_id=${clientId}` : null
  );

  const [range, setRange] = useState(30);
  const loading = txnLoading || acctLoading;
  const allTxns = transactions || [];
  const allAccounts = accounts || [];

  // Aggregate transactions by day for chart
  const dailyData = useMemo(() => {
    const now = new Date();
    const cutoff = new Date();
    cutoff.setDate(now.getDate() - range);

    const byDay: Record<string, number> = {};

    // Initialize all days in range
    for (let i = range - 1; i >= 0; i--) {
      const d = new Date();
      d.setDate(now.getDate() - i);
      const key = d.toISOString().split("T")[0];
      byDay[key] = 0;
    }

    // Sum ad_amount for completed topup/spend transactions
    allTxns.forEach((txn) => {
      if (txn.status !== "completed") return;
      const txnDate = new Date(txn.created_at);
      if (txnDate < cutoff) return;
      const key = txnDate.toISOString().split("T")[0];
      if (key in byDay) {
        // Use absolute value of negative spend amounts
        if (txn.ad_amount < 0) {
          byDay[key] += Math.abs(txn.ad_amount);
        }
      }
    });

    return Object.entries(byDay)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, amount]) => ({
        date: date.split("-").slice(1).join("/"),
        amount: Math.round(amount * 100) / 100,
      }));
  }, [allTxns, range]);

  const totalSpend = useMemo(
    () => dailyData.reduce((sum, d) => sum + d.amount, 0),
    [dailyData]
  );

  // Platform breakdown from accounts
  const platformBreakdown = useMemo(() => {
    const byPlatform: Record<string, number> = {};
    allAccounts.forEach((a) => {
      const p = a.platform;
      byPlatform[p] = (byPlatform[p] || 0) + a.total_spend;
    });
    return Object.entries(byPlatform).map(([name, total]) => ({ name, total }));
  }, [allAccounts]);

  const allTimeSpend = allAccounts.reduce((sum, a) => sum + a.total_spend, 0);

  const exportCSV = () => {
    const headers = "Date,Amount\n";
    const rows = dailyData
      .map((d) => `${d.date},${d.amount}`)
      .join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `adflux-spending-${range}d-${new Date().toISOString().split("T")[0]}.csv`;
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Spending Analytics</h1>
          <p className="text-gray-400">Track and analyze your ad spending</p>
        </div>
        <Button variant="outline" onClick={exportCSV}>
          <Download className="mr-2 h-4 w-4" />
          Export
        </Button>
      </div>

      {/* Date Range + Total */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex gap-2">
          {ranges.map((r) => (
            <Button
              key={r.value}
              variant={range === r.value ? "default" : "outline"}
              size="sm"
              onClick={() => setRange(r.value)}
            >
              {r.label}
            </Button>
          ))}
        </div>
        <Card className="flex-1">
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-violet-500">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Total Spend ({range} days)</p>
              <p className="text-xl font-bold text-white">{formatCurrency(totalSpend)}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Spending Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Daily Spending</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[350px]">
            {dailyData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" stroke="#6b7280" fontSize={12} tickLine={false} />
                  <YAxis stroke="#6b7280" fontSize={12} tickLine={false} tickFormatter={(v) => `$${v}`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: "8px" }}
                    labelStyle={{ color: "#9ca3af" }}
                    formatter={(value) => [`$${Number(value).toFixed(2)}`, "Spend"]}
                  />
                  <Bar dataKey="amount" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center">
                <p className="text-gray-400">No spending data available</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* By Account */}
        <Card>
          <CardHeader>
            <CardTitle>Breakdown by Account</CardTitle>
          </CardHeader>
          <CardContent>
            {allAccounts.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Account</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead className="text-right">Total Spend</TableHead>
                    <TableHead className="text-right">Daily Limit</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allAccounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell className="font-medium text-white">{account.name}</TableCell>
                      <TableCell>
                        <Badge
                          className={
                            account.platform.toLowerCase() === "google"
                              ? "bg-blue-600 text-white"
                              : account.platform.toLowerCase() === "meta"
                              ? "bg-indigo-600 text-white"
                              : "bg-pink-600 text-white"
                          }
                        >
                          {account.platform}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-white">
                        {formatCurrency(account.total_spend)}
                      </TableCell>
                      <TableCell className="text-right text-gray-300">
                        {formatCurrency(account.daily_limit)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="py-8 text-center text-gray-400">No accounts found.</p>
            )}
          </CardContent>
        </Card>

        {/* By Platform */}
        <Card>
          <CardHeader>
            <CardTitle>Breakdown by Platform</CardTitle>
          </CardHeader>
          <CardContent>
            {platformBreakdown.length > 0 ? (
              <div className="space-y-4">
                {platformBreakdown.map((platform) => {
                  const pct = allTimeSpend > 0 ? (platform.total / allTimeSpend) * 100 : 0;
                  const colorClass =
                    platform.name.toLowerCase() === "google"
                      ? "bg-blue-500"
                      : platform.name.toLowerCase() === "meta"
                      ? "bg-indigo-500"
                      : "bg-pink-500";
                  return (
                    <div key={platform.name} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">{platform.name}</span>
                        <span className="text-white">{formatCurrency(platform.total)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-gray-800">
                        <div
                          className={`h-full rounded-full ${colorClass}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-500">{pct.toFixed(1)}% of total</p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="py-8 text-center text-gray-400">No platform data available.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
