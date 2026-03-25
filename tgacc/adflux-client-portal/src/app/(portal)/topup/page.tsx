"use client";

import React, { useState, useMemo, useEffect } from "react";
import {
  DollarSign,
  Bitcoin,
  CheckCircle2,
  Wallet,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useApi, useApiToken, apiFetch } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency, formatDateTime } from "@/lib/utils";

interface ClientInfo {
  id: string;
  name: string;
  plan: string;
  niche: string;
  [key: string]: any;
}

interface Transaction {
  id: string;
  type: string;
  ad_amount: number;
  commission: number;
  crypto_amount: number;
  crypto_currency: string;
  status: string;
  notes: string;
  created_at: string;
}

interface CurrenciesResponse {
  currencies: string[];
}

interface CommissionResponse {
  base_rate: number;
  effective_rate: number;
  commission: number;
  total: number;
  [key: string]: any;
}

interface InvoiceResponse {
  invoice_id: string;
  invoice_url: string;
  order_id: string;
  ad_spend: number;
  commission: number;
  total: number;
  rate_pct: number;
  pay_currency: string;
}

const tierInfo: Record<string, { name: string; color: string }> = {
  starter: { name: "Starter", color: "from-gray-500 to-gray-600" },
  growth: { name: "Growth", color: "from-blue-500 to-blue-600" },
  scale: { name: "Scale", color: "from-violet-500 to-violet-600" },
  enterprise: { name: "Enterprise", color: "from-amber-500 to-amber-600" },
};

export default function TopUpPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const token = useApiToken();

  const { data: clientInfo, loading: clientLoading } = useApi<ClientInfo>(
    clientId ? `/clients/${clientId}` : null
  );
  const { data: currenciesData, loading: currLoading } = useApi<CurrenciesResponse>(
    "/payments/currencies"
  );
  const { data: transactions, loading: txnLoading } = useApi<Transaction[]>(
    clientId ? `/payments/transactions?client_id=${clientId}` : null
  );

  const [amount, setAmount] = useState("1000");
  const [crypto, setCrypto] = useState("");
  const [commissionData, setCommissionData] = useState<CommissionResponse | null>(null);
  const [commissionLoading, setCommissionLoading] = useState(false);
  const [invoiceData, setInvoiceData] = useState<InvoiceResponse | null>(null);
  const [invoiceLoading, setInvoiceLoading] = useState(false);
  const [invoiceError, setInvoiceError] = useState<string | null>(null);

  const plan = clientInfo?.plan || "starter";
  const niche = clientInfo?.niche || "";
  const tier = tierInfo[plan] || tierInfo.starter;
  const currencies = currenciesData?.currencies || [];
  const numAmount = parseFloat(amount) || 0;

  // Set default crypto when currencies load
  useEffect(() => {
    if (currencies.length > 0 && !crypto) {
      setCrypto(currencies[0]);
    }
  }, [currencies, crypto]);

  // Fetch commission preview when amount or plan changes
  useEffect(() => {
    if (!token || numAmount < 100 || !plan) return;
    const controller = new AbortController();
    setCommissionLoading(true);
    apiFetch<CommissionResponse>("/payments/commission", token, {
      method: "POST",
      body: JSON.stringify({ amount: numAmount, plan, niche }),
      signal: controller.signal,
    })
      .then(setCommissionData)
      .catch(() => {})
      .finally(() => setCommissionLoading(false));
    return () => controller.abort();
  }, [numAmount, plan, niche, token]);

  const topupTransactions = useMemo(
    () => (transactions || []).filter((t) => t.type === "topup"),
    [transactions]
  );

  const commissionRate = commissionData?.effective_rate ?? commissionData?.base_rate ?? 0;
  const commissionAmount = commissionData?.commission ?? numAmount * (commissionRate / 100);
  const total = commissionData?.total ?? numAmount + commissionAmount;

  const handleGenerateInvoice = async () => {
    if (!token || numAmount < 100) return;
    setInvoiceLoading(true);
    setInvoiceError(null);
    setInvoiceData(null);
    try {
      const result = await apiFetch<InvoiceResponse>("/payments/invoice", token, {
        method: "POST",
        body: JSON.stringify({
          amount: numAmount,
          plan,
          niche,
          pay_currency: crypto,
          order_description: `AdFlux top-up $${numAmount}`,
        }),
      });
      setInvoiceData(result);
    } catch (e: any) {
      setInvoiceError(e.message || "Failed to generate invoice");
    } finally {
      setInvoiceLoading(false);
    }
  };

  const loading = clientLoading || currLoading;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Crypto Top Up</h1>
        <p className="text-gray-400">Add funds to your AdFlux wallet</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top Up Form */}
        <div className="space-y-6">
          {/* Tier Display */}
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${tier.color}`}>
                    <Wallet className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Your Plan</p>
                    <p className="font-semibold text-white">{tier.name} Tier</p>
                  </div>
                </div>
                <Badge variant="outline" className="text-lg">
                  {commissionRate > 0 ? `${commissionRate}%` : "..."} Commission
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Amount Input */}
          <Card>
            <CardHeader>
              <CardTitle>Top Up Amount</CardTitle>
              <CardDescription>Enter the amount you want to add (USD)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="amount">Amount (USD)</Label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                  <Input
                    id="amount"
                    type="number"
                    min="100"
                    max="1000000"
                    className="pl-10 text-lg"
                    value={amount}
                    onChange={(e) => {
                      setAmount(e.target.value);
                      setInvoiceData(null);
                    }}
                  />
                </div>
                <p className="text-xs text-gray-500">Min: $100 — Max: $1,000,000</p>
              </div>

              <div className="flex flex-wrap gap-2">
                {[500, 1000, 2500, 5000, 10000].map((preset) => (
                  <Button
                    key={preset}
                    variant={amount === preset.toString() ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setAmount(preset.toString());
                      setInvoiceData(null);
                    }}
                  >
                    {formatCurrency(preset)}
                  </Button>
                ))}
              </div>

              <div className="space-y-2">
                <Label>Cryptocurrency</Label>
                <Select
                  value={crypto}
                  onValueChange={(v) => {
                    setCrypto(v);
                    setInvoiceData(null);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select currency" />
                  </SelectTrigger>
                  <SelectContent>
                    {currencies.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c.toUpperCase()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Commission Calculator */}
          <Card>
            <CardHeader>
              <CardTitle>Payment Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              {commissionLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Ad Spend Amount</span>
                    <span className="text-white">{formatCurrency(numAmount)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">
                      Commission ({commissionRate > 0 ? `${commissionRate}%` : "..."})
                    </span>
                    <span className="text-yellow-400">+{formatCurrency(commissionAmount)}</span>
                  </div>
                  <div className="border-t border-gray-800 pt-3">
                    <div className="flex justify-between font-semibold">
                      <span className="text-gray-200">Total (USD)</span>
                      <span className="text-white">{formatCurrency(total)}</span>
                    </div>
                  </div>
                </div>
              )}

              <Button
                className="mt-6 w-full"
                size="lg"
                onClick={handleGenerateInvoice}
                disabled={numAmount < 100 || invoiceLoading || !crypto}
              >
                {invoiceLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  "Generate Payment Link"
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Payment Info */}
        <div className="space-y-6">
          {invoiceData ? (
            <Card className="border-blue-800 bg-blue-950/30">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                  <CardTitle>Invoice Created</CardTitle>
                </div>
                <CardDescription>
                  Your payment invoice has been generated
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2 rounded-lg bg-gray-900 p-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Invoice ID</span>
                    <span className="font-mono text-white">{invoiceData.invoice_id}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Ad Spend</span>
                    <span className="text-white">{formatCurrency(invoiceData.ad_spend)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Commission ({invoiceData.rate_pct}%)</span>
                    <span className="text-yellow-400">+{formatCurrency(invoiceData.commission)}</span>
                  </div>
                  <div className="flex justify-between text-sm font-semibold">
                    <span className="text-gray-200">Total</span>
                    <span className="text-white">{formatCurrency(invoiceData.total)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Currency</span>
                    <span className="text-blue-400">{invoiceData.pay_currency.toUpperCase()}</span>
                  </div>
                </div>

                <a
                  href={invoiceData.invoice_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block"
                >
                  <Button className="w-full" size="lg">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Pay Now
                  </Button>
                </a>

                <div className="rounded-lg border border-yellow-800/50 bg-yellow-950/30 p-4">
                  <p className="text-sm text-yellow-300">
                    ⚠️ Complete the payment at the link above. Your balance will be credited after network confirmation (typically 5-30 minutes).
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : invoiceError ? (
            <Card className="border-red-800 bg-red-950/30">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <p className="text-lg font-medium text-red-400">Invoice Error</p>
                <p className="mt-2 text-sm text-red-400/70">{invoiceError}</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => setInvoiceError(null)}
                >
                  Try Again
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card className="flex h-[400px] items-center justify-center">
              <div className="text-center">
                <Bitcoin className="mx-auto h-16 w-16 text-gray-700" />
                <p className="mt-4 text-gray-400">Enter an amount and click</p>
                <p className="text-gray-400">&quot;Generate Payment Link&quot;</p>
                <p className="mt-2 text-sm text-gray-500">to create a payment invoice</p>
              </div>
            </Card>
          )}

          {/* Recent Top-ups */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Top-ups</CardTitle>
            </CardHeader>
            <CardContent>
              {txnLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                </div>
              ) : topupTransactions.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Crypto</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topupTransactions.map((txn) => (
                      <TableRow key={txn.id}>
                        <TableCell className="text-gray-300">{formatDateTime(txn.created_at)}</TableCell>
                        <TableCell className="text-right text-green-400">
                          +{formatCurrency(Math.abs(txn.ad_amount))}
                        </TableCell>
                        <TableCell>
                          {txn.crypto_currency ? (
                            <Badge variant="outline">{txn.crypto_currency.toUpperCase()}</Badge>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={txn.status === "completed" ? "success" : "warning"}>
                            {txn.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="py-8 text-center text-gray-400">No top-up history yet.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
