"use client";

import React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CreditCard,
  ExternalLink,
  TrendingUp,
  Calendar,
  Clock,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency, formatDate } from "@/lib/utils";

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

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="success">✅ Active</Badge>;
    case "banned":
      return <Badge variant="destructive">❌ Banned</Badge>;
    case "paused":
      return <Badge variant="warning">⏸️ Paused</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function getPlatformColor(platform: string) {
  const p = platform.toLowerCase();
  if (p === "google") return "from-blue-500 to-blue-600";
  if (p === "meta") return "from-indigo-500 to-indigo-600";
  if (p === "tiktok") return "from-pink-500 to-pink-600";
  return "from-gray-500 to-gray-600";
}

export default function AccountDetailPage() {
  const params = useParams();
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const { data: accounts, loading, error } = useApi<Account[]>(
    clientId ? `/accounts?client_id=${clientId}` : null
  );

  const account = (accounts || []).find((a) => a.id === params.id);

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
        <p className="text-lg text-red-400">Failed to load account</p>
        <p className="text-sm text-gray-500">{error}</p>
        <Link href="/accounts">
          <Button variant="ghost" className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Accounts
          </Button>
        </Link>
      </div>
    );
  }

  if (!account) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-lg text-gray-400">Account not found</p>
        <Link href="/accounts">
          <Button variant="ghost" className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Accounts
          </Button>
        </Link>
      </div>
    );
  }

  // Build status history from available data
  const statusHistory: { date: string; status: string; note: string }[] = [];
  if (account.created_at) {
    statusHistory.push({ date: account.created_at, status: "Created", note: "Account provisioned" });
  }
  if (account.status === "active") {
    statusHistory.push({ date: account.created_at, status: "Active", note: "Account is currently active" });
  }
  if (account.banned_at) {
    statusHistory.push({
      date: account.banned_at,
      status: "Banned",
      note: account.ban_reason || "Account suspended",
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/accounts">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">{account.name}</h1>
          <p className="text-gray-400">Account details and performance</p>
        </div>
      </div>

      {/* Account Info */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${getPlatformColor(account.platform)}`}>
                <ExternalLink className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Platform</p>
                <p className="font-semibold text-white">{account.platform}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Status</p>
                <div className="mt-1">{getStatusBadge(account.status)}</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600">
                <CreditCard className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Balance</p>
                <p className="font-semibold text-white">{formatCurrency(account.balance)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-amber-600">
                <TrendingUp className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Total Spend</p>
                <p className="font-semibold text-white">{formatCurrency(account.total_spend)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Ban Warning */}
      {account.status === "banned" && account.ban_reason && (
        <Card className="border-red-800 bg-red-950/30">
          <CardContent className="flex items-start gap-3 p-6">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div>
              <p className="font-medium text-red-300">Account Banned</p>
              <p className="mt-1 text-sm text-red-400/80">{account.ban_reason}</p>
              {account.banned_at && (
                <p className="mt-1 text-xs text-red-500">Banned on {formatDate(account.banned_at)}</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Account Details Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Account Details</CardTitle>
          <Link href="/topup">
            <Button size="sm">
              <CreditCard className="mr-2 h-4 w-4" />
              Top Up
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-gray-800 p-4">
              <p className="text-sm text-gray-400">Account ID</p>
              <p className="mt-1 font-mono text-sm text-white">{account.account_id || account.id}</p>
            </div>
            <div className="rounded-lg border border-gray-800 p-4">
              <p className="text-sm text-gray-400">Daily Limit</p>
              <p className="mt-1 font-semibold text-white">{formatCurrency(account.daily_limit)}</p>
            </div>
            <div className="rounded-lg border border-gray-800 p-4">
              <p className="text-sm text-gray-400">Created</p>
              <p className="mt-1 text-white">{formatDate(account.created_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Status History */}
      <Card>
        <CardHeader>
          <CardTitle>Status History</CardTitle>
        </CardHeader>
        <CardContent>
          {statusHistory.length > 0 ? (
            <div className="space-y-4">
              {statusHistory.map((event, index) => (
                <div key={index} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-700 bg-gray-800">
                      {index === 0 ? (
                        <Calendar className="h-4 w-4 text-blue-400" />
                      ) : (
                        <Clock className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                    {index < statusHistory.length - 1 && (
                      <div className="mt-1 h-full w-px bg-gray-800" />
                    )}
                  </div>
                  <div className="pb-4">
                    <p className="text-sm font-medium text-white">{event.status}</p>
                    <p className="text-xs text-gray-400">{event.note}</p>
                    <p className="mt-1 text-xs text-gray-500">{formatDate(event.date)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-4 text-center text-gray-400">No status history available.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
