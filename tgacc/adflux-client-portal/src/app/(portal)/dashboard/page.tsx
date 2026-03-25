"use client";

import React from "react";
import Link from "next/link";
import {
  DollarSign,
  TrendingUp,
  Layers,
  Clock,
  CreditCard,
  Eye,
  MessageCircle,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
} from "lucide-react";
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
import { formatCurrency, formatDateTime } from "@/lib/utils";

interface Account {
  id: string;
  client_id: string;
  platform: string;
  account_id: string;
  name: string;
  status: string;
  balance: number;
  total_spend: number;
  daily_limit: number;
  created_at: string;
  banned_at: string | null;
  ban_reason: string | null;
}

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

function getTransactionBadge(type: string) {
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

function getAccountStatusIcon(status: string) {
  switch (status) {
    case "active":
      return <span className="text-green-400">✅ Active</span>;
    case "banned":
      return <span className="text-red-400">❌ Banned</span>;
    case "paused":
      return <span className="text-yellow-400">⏸️ Paused</span>;
    default:
      return <span className="text-gray-400">{status}</span>;
  }
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const userName = session?.user?.name || "User";

  const { data: accounts, loading: accountsLoading } = useApi<Account[]>(
    clientId ? `/accounts?client_id=${clientId}` : null
  );
  const { data: transactions, loading: txnLoading } = useApi<Transaction[]>(
    clientId ? `/payments/transactions?client_id=${clientId}` : null
  );

  const loading = accountsLoading || txnLoading;
  const accts = accounts || [];
  const txns = transactions || [];

  const totalBalance = accts.reduce((sum, a) => sum + a.balance, 0);
  const totalSpend = accts.reduce((sum, a) => sum + a.total_spend, 0);
  const activeCount = accts.filter((a) => a.status === "active").length;
  const pendingTxns = txns.filter((t) => t.status === "pending");
  const pendingAmount = pendingTxns.reduce((sum, t) => sum + Math.abs(t.ad_amount), 0);
  const recentTransactions = txns.slice(0, 10);

  const statCards: {
    title: string;
    value: string;
    icon: typeof DollarSign;
    change: string;
    trend: "up" | "down" | "neutral";
    color: string;
  }[] = [
    {
      title: "Total Balance",
      value: formatCurrency(totalBalance),
      icon: DollarSign,
      change: `across ${accts.length} accounts`,
      trend: "neutral" as const,
      color: "from-blue-500 to-blue-600",
    },
    {
      title: "Total Spend",
      value: formatCurrency(totalSpend),
      icon: TrendingUp,
      change: "all time",
      trend: "up" as const,
      color: "from-violet-500 to-violet-600",
    },
    {
      title: "Active Accounts",
      value: activeCount.toString(),
      icon: Layers,
      change: "of " + accts.length + " total",
      trend: "neutral" as const,
      color: "from-emerald-500 to-emerald-600",
    },
    {
      title: "Pending Top-ups",
      value: pendingTxns.length.toString(),
      icon: Clock,
      change: formatCurrency(pendingAmount),
      trend: "neutral" as const,
      color: "from-amber-500 to-amber-600",
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Welcome back, {userName.split(" ")[0]} 👋
        </h1>
        <p className="text-gray-400">
          Here&apos;s an overview of your ad accounts and activity.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">{stat.title}</p>
                  <p className="mt-1 text-2xl font-bold text-white">{stat.value}</p>
                  <div className="mt-1 flex items-center gap-1 text-xs">
                    {stat.trend === "up" && (
                      <ArrowUpRight className="h-3 w-3 text-green-400" />
                    )}
                    {stat.trend === "down" && (
                      <ArrowDownRight className="h-3 w-3 text-red-400" />
                    )}
                    <span
                      className={
                        stat.trend === "up"
                          ? "text-green-400"
                          : stat.trend === "down"
                          ? "text-red-400"
                          : "text-gray-400"
                      }
                    >
                      {stat.change}
                    </span>
                  </div>
                </div>
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${stat.color} shadow-lg`}
                >
                  <stat.icon className="h-6 w-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <Link href="/topup">
          <Button>
            <CreditCard className="mr-2 h-4 w-4" />
            Top Up
          </Button>
        </Link>
        <Link href="/accounts">
          <Button variant="secondary">
            <Eye className="mr-2 h-4 w-4" />
            View Accounts
          </Button>
        </Link>
        <Link href="/support">
          <Button variant="outline">
            <MessageCircle className="mr-2 h-4 w-4" />
            Support
          </Button>
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Transactions */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent Transactions</CardTitle>
            <Link href="/billing">
              <Button variant="ghost" size="sm">
                View All
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentTransactions.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentTransactions.map((txn) => (
                    <TableRow key={txn.id}>
                      <TableCell className="text-gray-300">
                        {formatDateTime(txn.created_at)}
                      </TableCell>
                      <TableCell>{getTransactionBadge(txn.type)}</TableCell>
                      <TableCell
                        className={
                          txn.ad_amount >= 0 ? "text-green-400" : "text-red-400"
                        }
                      >
                        {txn.ad_amount >= 0 ? "+" : ""}
                        {formatCurrency(Math.abs(txn.ad_amount))}
                      </TableCell>
                      <TableCell>{getStatusBadge(txn.status)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="py-8 text-center text-gray-400">No transactions yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Account Status */}
        <Card>
          <CardHeader>
            <CardTitle>Account Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {accts.length > 0 ? (
              <>
                {accts.map((account) => (
                  <Link
                    key={account.id}
                    href={`/accounts/${account.id}`}
                    className="block rounded-lg border border-gray-800 p-3 transition-colors hover:border-gray-700 hover:bg-gray-800/50"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-white">
                          {account.name}
                        </p>
                        <p className="text-xs text-gray-400">{account.platform}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs">
                          {getAccountStatusIcon(account.status)}
                        </p>
                        <p className="text-xs text-gray-400">
                          {formatCurrency(account.balance)}
                        </p>
                      </div>
                    </div>
                  </Link>
                ))}

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 rounded-lg bg-gray-800/50 p-3">
                  <div className="text-center">
                    <p className="text-lg font-bold text-green-400">
                      {accts.filter((a) => a.status === "active").length}
                    </p>
                    <p className="text-xs text-gray-400">Active</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-yellow-400">
                      {accts.filter((a) => a.status === "paused").length}
                    </p>
                    <p className="text-xs text-gray-400">Paused</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-red-400">
                      {accts.filter((a) => a.status === "banned").length}
                    </p>
                    <p className="text-xs text-gray-400">Banned</p>
                  </div>
                </div>
              </>
            ) : (
              <p className="py-4 text-center text-gray-400">No accounts yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
