"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Search, Filter, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { useApi } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency } from "@/lib/utils";

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

function getPlatformBadge(platform: string) {
  const p = platform.toLowerCase();
  if (p === "google") return <Badge className="bg-blue-600 text-white">Google</Badge>;
  if (p === "meta") return <Badge className="bg-indigo-600 text-white">Meta</Badge>;
  if (p === "tiktok") return <Badge className="bg-pink-600 text-white">TikTok</Badge>;
  return <Badge variant="outline">{platform}</Badge>;
}

function getStatusDisplay(status: string) {
  switch (status) {
    case "active":
      return <span className="flex items-center gap-1.5 text-green-400"><span className="h-2 w-2 rounded-full bg-green-400" /> Active</span>;
    case "banned":
      return <span className="flex items-center gap-1.5 text-red-400"><span className="h-2 w-2 rounded-full bg-red-400" /> Banned</span>;
    case "paused":
      return <span className="flex items-center gap-1.5 text-yellow-400"><span className="h-2 w-2 rounded-full bg-yellow-400" /> Paused</span>;
    default:
      return <span className="flex items-center gap-1.5 text-gray-400"><span className="h-2 w-2 rounded-full bg-gray-400" /> {status}</span>;
  }
}

export default function AccountsPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const { data: accounts, loading, error } = useApi<Account[]>(
    clientId ? `/accounts?client_id=${clientId}` : null
  );

  const [platformFilter, setPlatformFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = (accounts || []).filter((account) => {
    if (platformFilter !== "all" && account.platform.toLowerCase() !== platformFilter.toLowerCase()) return false;
    if (statusFilter !== "all" && account.status !== statusFilter) return false;
    if (search && !account.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

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
        <p className="text-lg text-red-400">Failed to load accounts</p>
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Ad Accounts</h1>
        <p className="text-gray-400">Manage and monitor your advertising accounts</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>All Accounts</CardTitle>
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <Input
                  placeholder="Search accounts..."
                  className="w-[200px] pl-10"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <Select value={platformFilter} onValueChange={setPlatformFilter}>
                <SelectTrigger className="w-[140px]">
                  <Filter className="mr-2 h-4 w-4" />
                  <SelectValue placeholder="Platform" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Platforms</SelectItem>
                  <SelectItem value="google">Google</SelectItem>
                  <SelectItem value="meta">Meta</SelectItem>
                  <SelectItem value="tiktok">TikTok</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="paused">Paused</SelectItem>
                  <SelectItem value="banned">Banned</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Account Name</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Balance</TableHead>
                <TableHead className="text-right">Daily Limit</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((account) => (
                <TableRow key={account.id} className="cursor-pointer">
                  <TableCell>
                    <Link href={`/accounts/${account.id}`} className="font-medium text-white hover:text-blue-400">
                      {account.name}
                    </Link>
                  </TableCell>
                  <TableCell>{getPlatformBadge(account.platform)}</TableCell>
                  <TableCell>{getStatusDisplay(account.status)}</TableCell>
                  <TableCell className="text-right text-white">
                    {formatCurrency(account.balance)}
                  </TableCell>
                  <TableCell className="text-right text-gray-300">
                    {formatCurrency(account.daily_limit)}
                  </TableCell>
                  <TableCell>
                    <Link href={`/accounts/${account.id}`}>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-gray-400">
                    No accounts found matching your filters.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
