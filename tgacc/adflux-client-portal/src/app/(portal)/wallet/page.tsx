"use client";

import React, { useState } from "react";
import {
  Wallet2,
  ArrowUpCircle,
  ArrowDownCircle,
  ArrowRightLeft,
  Loader2,
  Plus,
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
import { useApi, useApiToken, apiFetch } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency, formatDateTime } from "@/lib/utils";

interface WalletInfo {
  balance: number;
  currency: string;
  [key: string]: any;
}

interface WalletTransaction {
  id: string;
  type: string;
  amount: number;
  currency: string;
  status: string;
  notes: string;
  created_at: string;
  [key: string]: any;
}

function getTypeBadge(type: string) {
  switch (type) {
    case "deposit":
      return <Badge variant="success">Deposit</Badge>;
    case "withdrawal":
      return <Badge variant="destructive">Withdrawal</Badge>;
    case "transfer":
      return <Badge className="bg-sky-600 text-white">Transfer</Badge>;
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

function getTypeIcon(type: string) {
  switch (type) {
    case "deposit":
      return <ArrowDownCircle className="h-4 w-4 text-green-400" />;
    case "withdrawal":
      return <ArrowUpCircle className="h-4 w-4 text-red-400" />;
    case "transfer":
      return <ArrowRightLeft className="h-4 w-4 text-sky-400" />;
    default:
      return <ArrowRightLeft className="h-4 w-4 text-gray-400" />;
  }
}

export default function WalletPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const token = useApiToken();

  const {
    data: wallet,
    loading: walletLoading,
    error: walletError,
    refetch: refetchWallet,
  } = useApi<WalletInfo>(clientId ? "/wallet/" : null);

  const {
    data: transactions,
    loading: txnLoading,
    error: txnError,
    refetch: refetchTxns,
  } = useApi<WalletTransaction[]>(clientId ? "/wallet/transactions" : null);

  const [showDeposit, setShowDeposit] = useState(false);
  const [depositAmount, setDepositAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("usdt");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const loading = walletLoading || txnLoading;
  const error = walletError || txnError;
  const txns = transactions || [];

  const handleDeposit = async () => {
    if (!depositAmount || !token) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await apiFetch("/wallet/deposit", token, {
        method: "POST",
        body: JSON.stringify({
          amount: parseFloat(depositAmount),
          payment_method: paymentMethod,
        }),
      });
      setShowDeposit(false);
      setDepositAmount("");
      refetchWallet();
      refetchTxns();
    } catch (e: any) {
      setSubmitError(e.message || "Failed to submit deposit");
    } finally {
      setSubmitting(false);
    }
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
        <p className="text-lg text-red-400">Failed to load wallet</p>
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Wallet</h1>
          <p className="text-gray-400">Manage your funds and view transaction history</p>
        </div>
        <Button onClick={() => setShowDeposit(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Deposit
        </Button>
      </div>

      {/* Balance Card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 shadow-lg">
              <Wallet2 className="h-7 w-7 text-white" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Current Balance</p>
              <p className="text-3xl font-bold text-white">
                {formatCurrency(wallet?.balance ?? 0)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Deposit Modal */}
      {showDeposit && (
        <Card className="border-blue-800 bg-gray-900">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Deposit Funds</CardTitle>
            <button
              onClick={() => {
                setShowDeposit(false);
                setSubmitError(null);
              }}
              className="text-gray-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm text-gray-400">Amount (USD)</label>
              <Input
                type="number"
                placeholder="Enter amount"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                min="1"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm text-gray-400">Payment Method</label>
              <Select value={paymentMethod} onValueChange={setPaymentMethod}>
                <SelectTrigger>
                  <SelectValue placeholder="Select method" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="usdt">USDT (Tether)</SelectItem>
                  <SelectItem value="usdc">USDC</SelectItem>
                  <SelectItem value="btc">Bitcoin (BTC)</SelectItem>
                  <SelectItem value="eth">Ethereum (ETH)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {submitError && (
              <p className="text-sm text-red-400">{submitError}</p>
            )}
            <Button
              onClick={handleDeposit}
              disabled={!depositAmount || submitting}
              className="w-full"
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {submitting ? "Processing..." : "Submit Deposit"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Transaction History */}
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          {txns.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {txns.map((txn) => (
                  <TableRow key={txn.id}>
                    <TableCell className="whitespace-nowrap text-gray-300">
                      {formatDateTime(txn.created_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getTypeIcon(txn.type)}
                        {getTypeBadge(txn.type)}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-gray-300">
                      {txn.notes || "—"}
                    </TableCell>
                    <TableCell
                      className={`text-right ${
                        txn.type === "deposit" ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {txn.type === "deposit" ? "+" : "-"}
                      {formatCurrency(Math.abs(txn.amount))}
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
    </div>
  );
}
