"use client";

import React, { useState } from "react";
import {
  Users,
  Copy,
  Check,
  DollarSign,
  UserPlus,
  Clock,
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
import { formatCurrency, formatDate } from "@/lib/utils";

interface AffiliateCode {
  code: string;
  url?: string;
  [key: string]: any;
}

interface AffiliateStats {
  total_referrals: number;
  total_earnings: number;
  pending_earnings: number;
  [key: string]: any;
}

interface Referral {
  id: string;
  name?: string;
  email?: string;
  status: string;
  earned: number;
  created_at: string;
  [key: string]: any;
}

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="success">Active</Badge>;
    case "pending":
      return <Badge variant="warning">Pending</Badge>;
    case "inactive":
      return <Badge variant="secondary">Inactive</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function AffiliatePage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;

  const { data: codeData, loading: codeLoading } = useApi<AffiliateCode>(
    clientId ? "/affiliate/code" : null
  );
  const { data: stats, loading: statsLoading } = useApi<AffiliateStats>(
    clientId ? "/affiliate/stats" : null
  );
  const { data: referrals, loading: refsLoading } = useApi<Referral[]>(
    clientId ? "/affiliate/referrals" : null
  );

  const [copied, setCopied] = useState(false);

  const loading = codeLoading || statsLoading || refsLoading;
  const refs = referrals || [];

  const handleCopy = () => {
    const text = codeData?.url || codeData?.code || "";
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
      <div>
        <h1 className="text-2xl font-bold text-white">Affiliate Program</h1>
        <p className="text-gray-400">Refer clients and earn commissions on their spending</p>
      </div>

      {/* Affiliate Code */}
      {codeData && (
        <Card className="border-blue-800/50">
          <CardContent className="p-6">
            <p className="mb-2 text-sm text-gray-400">Your Affiliate Code</p>
            <div className="flex items-center gap-3">
              <code className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 font-mono text-lg text-white">
                {codeData.url || codeData.code}
              </code>
              <Button variant="outline" onClick={handleCopy}>
                {copied ? (
                  <>
                    <Check className="mr-2 h-4 w-4 text-green-400" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Total Referrals</p>
                <p className="mt-1 text-2xl font-bold text-white">
                  {stats?.total_referrals ?? 0}
                </p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg">
                <UserPlus className="h-6 w-6 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Total Earnings</p>
                <p className="mt-1 text-2xl font-bold text-white">
                  {formatCurrency(stats?.total_earnings ?? 0)}
                </p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-lg">
                <DollarSign className="h-6 w-6 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Pending Earnings</p>
                <p className="mt-1 text-2xl font-bold text-white">
                  {formatCurrency(stats?.pending_earnings ?? 0)}
                </p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 shadow-lg">
                <Clock className="h-6 w-6 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Referral List */}
      <Card>
        <CardHeader>
          <CardTitle>Referrals</CardTitle>
        </CardHeader>
        <CardContent>
          {refs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Earned</TableHead>
                  <TableHead>Referred On</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {refs.map((ref) => (
                  <TableRow key={ref.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium text-white">
                          {ref.name || "—"}
                        </p>
                        {ref.email && (
                          <p className="text-xs text-gray-400">{ref.email}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(ref.status)}</TableCell>
                    <TableCell className="text-right text-green-400">
                      {formatCurrency(ref.earned)}
                    </TableCell>
                    <TableCell className="text-gray-300">
                      {formatDate(ref.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <Users className="h-12 w-12 text-gray-700" />
              <p className="mt-3 text-gray-400">No referrals yet</p>
              <p className="text-sm text-gray-500">
                Share your affiliate code to start earning
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
