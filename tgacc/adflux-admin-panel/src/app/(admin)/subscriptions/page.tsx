"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Modal } from "@/components/ui/modal"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Loader2, Plus, CreditCard, Users, DollarSign, Package } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatCurrency, formatDate } from "@/lib/utils"

interface Plan {
  id: string
  name: string
  price: number
  interval: string
  features: string[]
  active: boolean
  created_at: string
}

interface Subscription {
  id: string
  client_id: string
  client_name: string
  plan_id: string
  plan_name: string
  status: string
  current_period_start: string
  current_period_end: string
  created_at: string
}

const statusVariant: Record<string, string> = {
  active: "success",
  canceled: "destructive",
  past_due: "warning",
  trialing: "info",
  paused: "secondary",
}

export default function SubscriptionsPage() {
  const [addPlanOpen, setAddPlanOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const token = useApiToken()
  const { data: plans, loading: plansLoading, error: plansError, refetch: refetchPlans } = useApi<Plan[]>("/admin/plans")
  const { data: subscriptions, loading: subsLoading, error: subsError, refetch: refetchSubs } = useApi<Subscription[]>("/admin/subscriptions")

  const loading = plansLoading || subsLoading
  const error = plansError || subsError

  // Plan form state
  const [formPlanName, setFormPlanName] = useState("")
  const [formPrice, setFormPrice] = useState("")
  const [formInterval, setFormInterval] = useState("monthly")
  const [formFeatures, setFormFeatures] = useState("")

  const resetForm = () => {
    setFormPlanName("")
    setFormPrice("")
    setFormInterval("monthly")
    setFormFeatures("")
    setFormError(null)
  }

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setFormError(null)
    try {
      await apiFetch("/admin/plans", token, {
        method: "POST",
        body: JSON.stringify({
          name: formPlanName,
          price: parseFloat(formPrice),
          interval: formInterval,
          features: formFeatures.split(",").map((f) => f.trim()).filter(Boolean),
        }),
      })
      setAddPlanOpen(false)
      resetForm()
      refetchPlans()
    } catch (err: any) {
      setFormError(err.message || "Failed to create plan")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading subscriptions…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load data: {error}</p>
        <Button variant="outline" onClick={refetchPlans}>Retry</Button>
      </div>
    )
  }

  const planList = plans ?? []
  const subsList = subscriptions ?? []
  const activeSubs = subsList.filter((s) => s.status === "active")

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <CreditCard className="h-6 w-6" /> Subscriptions
      </h1>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Plans</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <Package className="h-4 w-4 text-blue-400" /> {planList.length}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Active Subscriptions</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <Users className="h-4 w-4 text-emerald-400" /> {activeSubs.length}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Total Subscriptions</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-violet-400" /> {subsList.length}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">MRR (est.)</span>
            <span className="text-xl font-bold flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-amber-400" />
              {formatCurrency(
                activeSubs.reduce((sum, s) => {
                  const plan = planList.find((p) => p.id === s.plan_id)
                  return sum + (plan?.price ?? 0)
                }, 0)
              )}
            </span>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="plans">
        <TabsList>
          <TabsTrigger value="plans">Plans</TabsTrigger>
          <TabsTrigger value="subscriptions">Active Subscriptions</TabsTrigger>
        </TabsList>

        <TabsContent value="plans">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Plan Management</CardTitle>
                <Button size="sm" onClick={() => setAddPlanOpen(true)}>
                  <Plus className="h-3 w-3 mr-2" /> Create Plan
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {planList.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No plans created yet</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>Interval</TableHead>
                      <TableHead>Features</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {planList.map((plan) => (
                      <TableRow key={plan.id}>
                        <TableCell className="font-medium">{plan.name}</TableCell>
                        <TableCell className="font-bold">{formatCurrency(plan.price)}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{plan.interval}</Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
                          {(plan.features ?? []).join(", ") || "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={plan.active ? "success" : "secondary"}>
                            {plan.active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(plan.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="subscriptions">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Active Subscriptions</CardTitle>
            </CardHeader>
            <CardContent>
              {subsList.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No subscriptions found</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Client</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Period Start</TableHead>
                      <TableHead>Period End</TableHead>
                      <TableHead>Started</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {subsList.map((sub) => (
                      <TableRow key={sub.id}>
                        <TableCell className="font-medium">
                          {sub.client_name || sub.client_id}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{sub.plan_name || sub.plan_id}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={(statusVariant[sub.status] ?? "secondary") as any}>
                            {sub.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(sub.current_period_start)}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(sub.current_period_end)}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(sub.created_at)}
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

      {/* Create Plan Modal */}
      <Modal
        open={addPlanOpen}
        onClose={() => {
          setAddPlanOpen(false)
          resetForm()
        }}
        title="Create Plan"
      >
        <form className="space-y-4" onSubmit={handleCreatePlan}>
          {formError && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">
              {formError}
            </div>
          )}
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
              Plan Name
            </label>
            <Input
              placeholder="e.g. Pro Plan"
              value={formPlanName}
              onChange={(e) => setFormPlanName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
              Price (USD)
            </label>
            <Input
              type="number"
              placeholder="99.00"
              value={formPrice}
              onChange={(e) => setFormPrice(e.target.value)}
              required
              min="0"
              step="0.01"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
              Billing Interval
            </label>
            <Select
              value={formInterval}
              onChange={(e) => setFormInterval(e.target.value)}
              options={[
                { value: "monthly", label: "Monthly" },
                { value: "quarterly", label: "Quarterly" },
                { value: "yearly", label: "Yearly" },
              ]}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
              Features (comma-separated)
            </label>
            <Input
              placeholder="Feature 1, Feature 2, Feature 3"
              value={formFeatures}
              onChange={(e) => setFormFeatures(e.target.value)}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAddPlanOpen(false)
                resetForm()
              }}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Creating…
                </>
              ) : (
                "Create Plan"
              )}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
