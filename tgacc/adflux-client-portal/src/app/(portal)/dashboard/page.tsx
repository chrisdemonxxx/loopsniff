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
import {
  FadeIn,
  StaggerChildren,
  StaggerItem,
  AnimatedCounter,
  SpotlightCard,
} from "@/components/motion";

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
      return (
        <span className="flex items-center gap-1.5 text-xs">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-emerald-400">Completed</span>
        </span>
      );
    case "pending":
      return (
        <span className="flex items-center gap-1.5 text-xs">
          <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
          <span className="text-amber-400">Pending</span>
        </span>
      );
    case "failed":
      return (
        <span className="flex items-center gap-1.5 text-xs">
          <span className="h-2 w-2 rounded-full bg-red-400" />
          <span className="text-red-400">Failed</span>
        </span>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function getAccountStatusIcon(status: string) {
  switch (status) {
    case "active":
      return (
        <span className="flex items-center gap-1.5 text-xs">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-emerald-400">Active</span>
        </span>
      );
    case "banned":
      return (
        <span className="flex items-center gap-1.5 text-xs">
          <span className="h-2 w-2 rounded-full bg-red-400" />
          <span className="text-red-400">Banned</span>
        </span>
      );
    case "paused":
      return (
        <span className="flex items-center gap-1.5 text-xs">
          <span className="h-2 w-2 rounded-full bg-yellow-400" />
          <span className="text-yellow-400">Paused</span>
        </span>
      );
    default:
      return <span className="text-zinc-400">{status}</span>;
  }
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const userName = session?.user?.name || "User";

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

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
  const pendingAmount = pendingTxns.reduce(
    (sum, t) => sum + Math.abs(t.ad_amount),
    0
  );
  const recentTransactions = txns.slice(0, 10);

  const statCards: {
    title: string;
    numericValue: number;
    icon: typeof DollarSign;
    change: string;
    trend: "up" | "down" | "neutral";
    color: string;
    iconBg: string;
    prefix: string;
    suffix: string;
    decimals: number;
    borderColor: string;
  }[] = [
    {
      title: "Total Balance",
      numericValue: totalBalance,
      icon: DollarSign,
      change: `across ${accts.length} accounts`,
      trend: "neutral",
      color: "from-blue-500 to-blue-600",
      iconBg: "bg-blue-500/10",
      prefix: "$",
      suffix: "",
      decimals: 2,
      borderColor: "from-blue-500 via-blue-400 to-transparent",
    },
    {
      title: "Total Spend",
      numericValue: totalSpend,
      icon: TrendingUp,
      change: "all time",
      trend: "up",
      color: "from-violet-500 to-violet-600",
      iconBg: "bg-violet-500/10",
      prefix: "$",
      suffix: "",
      decimals: 2,
      borderColor: "from-violet-500 via-violet-400 to-transparent",
    },
    {
      title: "Active Accounts",
      numericValue: activeCount,
      icon: Layers,
      change: "of " + accts.length + " total",
      trend: "neutral",
      color: "from-emerald-500 to-emerald-600",
      iconBg: "bg-emerald-500/10",
      prefix: "",
      suffix: "",
      decimals: 0,
      borderColor: "from-emerald-500 via-emerald-400 to-transparent",
    },
    {
      title: "Pending Top-ups",
      numericValue: pendingTxns.length,
      icon: Clock,
      change: formatCurrency(pendingAmount),
      trend: "neutral",
      color: "from-amber-500 to-amber-600",
      iconBg: "bg-amber-500/10",
      prefix: "",
      suffix: "",
      decimals: 0,
      borderColor: "from-amber-500 via-amber-400 to-transparent",
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
    <div className="space-y-8">
      {/* Personalized Greeting */}
      <FadeIn>
        <div>
          <h1 className="text-3xl font-bold text-white">
            {greeting},{" "}
            <span className="text-gradient">{userName.split(" ")[0]}</span> 👋
          </h1>
          <p className="mt-1 text-zinc-400">
            Here&apos;s an overview of your ad accounts and activity.
          </p>
        </div>
      </FadeIn>

      {/* Stat Cards */}
      <StaggerChildren className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <StaggerItem key={stat.title}>
            <SpotlightCard className="h-full rounded-2xl">
              <Card className="glass-card h-full overflow-hidden border-0">
                {/* Gradient top border line */}
                <div
                  className={`h-[2px] bg-gradient-to-r ${stat.borderColor}`}
                />
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-zinc-400">
                        {stat.title}
                      </p>
                      <AnimatedCounter
                        value={stat.numericValue}
                        prefix={stat.prefix}
                        suffix={stat.suffix}
                        decimals={stat.decimals}
                        className="text-2xl font-bold text-white"
                      />
                      <div className="flex items-center gap-1 pt-0.5 text-xs">
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
                              : "text-zinc-500"
                          }
                        >
                          {stat.change}
                        </span>
                      </div>
                    </div>
                    <div
                      className={`flex h-12 w-12 items-center justify-center rounded-2xl ${stat.iconBg}`}
                    >
                      <stat.icon
                        className={`h-6 w-6 bg-gradient-to-br ${stat.color} bg-clip-text text-transparent`}
                        style={{ stroke: "url(#icon-gradient)" }}
                      />
                      <svg width="0" height="0" className="absolute">
                        <defs>
                          <linearGradient
                            id="icon-gradient"
                            x1="0%"
                            y1="0%"
                            x2="100%"
                            y2="100%"
                          >
                            <stop offset="0%" stopColor="currentColor" />
                            <stop offset="100%" stopColor="currentColor" />
                          </linearGradient>
                        </defs>
                      </svg>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </SpotlightCard>
          </StaggerItem>
        ))}
      </StaggerChildren>

      {/* Quick Actions */}
      <FadeIn delay={0.2}>
        <div className="flex flex-wrap gap-3">
          <Link href="/topup">
            <div className="glass-card group flex cursor-pointer items-center gap-2 rounded-xl px-5 py-3 transition-all hover:glow-blue">
              <CreditCard className="h-4 w-4 text-blue-400 transition-transform group-hover:scale-110" />
              <span className="text-sm font-medium text-white">Top Up</span>
            </div>
          </Link>
          <Link href="/accounts">
            <div className="glass-card group flex cursor-pointer items-center gap-2 rounded-xl px-5 py-3 transition-all hover:glow-emerald">
              <Eye className="h-4 w-4 text-emerald-400 transition-transform group-hover:scale-110" />
              <span className="text-sm font-medium text-white">
                View Accounts
              </span>
            </div>
          </Link>
          <Link href="/support">
            <div className="glass-card group flex cursor-pointer items-center gap-2 rounded-xl px-5 py-3 transition-all">
              <MessageCircle className="h-4 w-4 text-violet-400 transition-transform group-hover:scale-110" />
              <span className="text-sm font-medium text-white">Support</span>
            </div>
          </Link>
        </div>
      </FadeIn>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Transactions */}
        <FadeIn className="lg:col-span-2" delay={0.1}>
          <Card className="glass-card border-0">
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
                    <TableRow className="border-zinc-800/50">
                      <TableHead className="text-zinc-500">Date</TableHead>
                      <TableHead className="text-zinc-500">Type</TableHead>
                      <TableHead className="text-zinc-500">Amount</TableHead>
                      <TableHead className="text-zinc-500">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recentTransactions.map((txn) => (
                      <TableRow
                        key={txn.id}
                        className="border-zinc-800/50 transition-colors hover:bg-white/[0.02]"
                      >
                        <TableCell className="text-zinc-300">
                          {formatDateTime(txn.created_at)}
                        </TableCell>
                        <TableCell>
                          {getTransactionBadge(txn.type)}
                        </TableCell>
                        <TableCell
                          className={
                            txn.ad_amount >= 0
                              ? "font-medium text-green-400"
                              : "font-medium text-red-400"
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
                <p className="py-8 text-center text-zinc-400">
                  No transactions yet.
                </p>
              )}
            </CardContent>
          </Card>
        </FadeIn>

        {/* Account Status */}
        <FadeIn delay={0.2}>
          <Card className="glass-card border-0">
            <CardHeader>
              <CardTitle>Account Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {accts.length > 0 ? (
                <>
                  {accts.map((account) => (
                    <Link
                      key={account.id}
                      href={`/accounts/${account.id}`}
                      className="block rounded-xl border border-zinc-800/50 p-3 transition-all hover:border-zinc-700 hover:bg-white/[0.02]"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-white">
                            {account.name}
                          </p>
                          <p className="text-xs text-zinc-500">
                            {account.platform}
                          </p>
                        </div>
                        <div className="text-right">
                          <div>{getAccountStatusIcon(account.status)}</div>
                          <p className="mt-0.5 text-xs text-zinc-400">
                            {formatCurrency(account.balance)}
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))}

                  <div className="grid grid-cols-3 gap-2 rounded-xl bg-zinc-800/30 p-3">
                    <div className="text-center">
                      <p className="text-lg font-bold text-green-400">
                        {accts.filter((a) => a.status === "active").length}
                      </p>
                      <p className="text-xs text-zinc-500">Active</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-yellow-400">
                        {accts.filter((a) => a.status === "paused").length}
                      </p>
                      <p className="text-xs text-zinc-500">Paused</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-red-400">
                        {accts.filter((a) => a.status === "banned").length}
                      </p>
                      <p className="text-xs text-zinc-500">Banned</p>
                    </div>
                  </div>
                </>
              ) : (
                <p className="py-4 text-center text-zinc-400">
                  No accounts yet.
                </p>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      </div>
    </div>
  );
}
