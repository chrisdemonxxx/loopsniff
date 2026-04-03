"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Modal } from "@/components/ui/modal"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Search, Loader2, Link2, DollarSign, Users, CheckCircle2 } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatCurrency, formatDate } from "@/lib/utils"

interface Affiliate {
  id: string
  code: string
  name: string
  email: string
  total_referrals: number
  total_commission: number
  status: string
  created_at: string
}

interface Referral {
  id: string
  affiliate_id: string
  affiliate_code: string
  referred_client: string
  status: string
  commission: number
  approved: boolean
  created_at: string
}

const statusVariant: Record<string, string> = {
  active: "success",
  inactive: "secondary",
  suspended: "destructive",
  pending: "warning",
  approved: "success",
  rejected: "destructive",
}

export default function AffiliatesPage() {
  const [search, setSearch] = useState("")
  const [approving, setApproving] = useState<string | null>(null)

  const token = useApiToken()
  const { data: affiliates, loading: affLoading, error: affError, refetch: refetchAff } = useApi<Affiliate[]>("/admin/affiliates")
  const { data: referrals, loading: refLoading, error: refError, refetch: refetchRef } = useApi<Referral[]>("/admin/referrals")

  const loading = affLoading || refLoading
  const error = affError || refError

  const handleApprove = async (referralId: string) => {
    if (!token) return
    setApproving(referralId)
    try {
      await apiFetch(`/admin/referrals/${referralId}/approve`, token, { method: "POST" })
      refetchRef()
    } catch (err: any) {
      alert(err.message || "Failed to approve")
    } finally {
      setApproving(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading affiliates…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load affiliates: {error}</p>
        <Button variant="outline" onClick={refetchAff}>Retry</Button>
      </div>
    )
  }

  const affList = affiliates ?? []
  const refList = referrals ?? []
  const pendingRefs = refList.filter((r) => !r.approved && r.status === "pending")

  const filteredAffiliates = affList.filter(
    (a) =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.code.toLowerCase().includes(search.toLowerCase()) ||
      a.email.toLowerCase().includes(search.toLowerCase())
  )

  const totalCommission = affList.reduce((s, a) => s + (a.total_commission ?? 0), 0)
  const totalReferrals = affList.reduce((s, a) => s + (a.total_referrals ?? 0), 0)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Affiliate Management</h1>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Total Affiliates</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <Link2 className="h-4 w-4 text-blue-400" /> {affList.length}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Total Referrals</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <Users className="h-4 w-4 text-violet-400" /> {totalReferrals}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Total Commission</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-emerald-400" /> {formatCurrency(totalCommission)}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Pending Approvals</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-amber-400" /> {pendingRefs.length}
            </span>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="affiliates">
        <TabsList>
          <TabsTrigger value="affiliates">Affiliate Codes</TabsTrigger>
          <TabsTrigger value="referrals">Referral Tracking</TabsTrigger>
          <TabsTrigger value="approvals">Commission Approvals ({pendingRefs.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="affiliates">
          <Card>
            <CardHeader>
              <div className="relative max-w-sm">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search affiliates..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </CardHeader>
            <CardContent>
              {filteredAffiliates.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No affiliates found</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Referrals</TableHead>
                      <TableHead>Commission</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Joined</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAffiliates.map((aff) => (
                      <TableRow key={aff.id}>
                        <TableCell className="font-mono text-xs">{aff.code}</TableCell>
                        <TableCell className="font-medium">{aff.name}</TableCell>
                        <TableCell className="text-muted-foreground">{aff.email}</TableCell>
                        <TableCell>{aff.total_referrals}</TableCell>
                        <TableCell className="text-emerald-400 font-medium">
                          {formatCurrency(aff.total_commission)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={(statusVariant[aff.status] ?? "secondary") as any}>
                            {aff.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(aff.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="referrals">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">All Referrals</CardTitle>
            </CardHeader>
            <CardContent>
              {refList.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No referrals yet</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Affiliate Code</TableHead>
                      <TableHead>Referred Client</TableHead>
                      <TableHead>Commission</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {refList.map((ref) => (
                      <TableRow key={ref.id}>
                        <TableCell className="font-mono text-xs">{ref.affiliate_code}</TableCell>
                        <TableCell className="font-medium">{ref.referred_client}</TableCell>
                        <TableCell className="text-emerald-400">
                          {formatCurrency(ref.commission)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={(statusVariant[ref.status] ?? "secondary") as any}>
                            {ref.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(ref.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="approvals">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pending Commission Approvals</CardTitle>
            </CardHeader>
            <CardContent>
              {pendingRefs.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">
                  No pending approvals
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Affiliate Code</TableHead>
                      <TableHead>Referred Client</TableHead>
                      <TableHead>Commission</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingRefs.map((ref) => (
                      <TableRow key={ref.id}>
                        <TableCell className="font-mono text-xs">{ref.affiliate_code}</TableCell>
                        <TableCell className="font-medium">{ref.referred_client}</TableCell>
                        <TableCell className="text-emerald-400 font-medium">
                          {formatCurrency(ref.commission)}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(ref.created_at)}
                        </TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            onClick={() => handleApprove(ref.id)}
                            disabled={approving === ref.id}
                          >
                            {approving === ref.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              "Approve"
                            )}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
