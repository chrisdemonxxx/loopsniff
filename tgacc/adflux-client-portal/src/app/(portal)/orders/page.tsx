"use client";

import React, { useState, useMemo } from "react";
import {
  Package,
  CreditCard,
  Clock,
  CheckCircle,
  XCircle,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi, apiFetch, useApiToken } from "@/lib/api";
import { useSession } from "next-auth/react";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";

/* ---------- types ---------- */

interface Order {
  id: string;
  client_id: string;
  order_type: "ad_account" | "topup" | "subscription";
  status: "pending" | "payment_received" | "processing" | "delivered" | "cancelled";
  amount: number;
  currency: string;
  notes?: string;
  created_at: string;
  delivered_at?: string | null;
}

interface Subscription {
  id: string;
  client_id: string;
  plan: "starter" | "growth" | "premium" | "enterprise";
  price: number;
  currency: string;
  interval: "monthly" | "yearly";
  status: "active" | "paused" | "cancelled";
  started_at: string;
  next_billing_at: string;
}

/* ---------- badge helpers ---------- */

const ORDER_TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  ad_account: { label: "Ad Account", className: "bg-blue-600 text-white" },
  topup: { label: "Top Up", className: "bg-green-600 text-white" },
  subscription: { label: "Subscription", className: "bg-purple-600 text-white" },
};

function OrderTypeBadge({ type }: { type: string }) {
  const cfg = ORDER_TYPE_CONFIG[type] ?? { label: type, className: "" };
  return <Badge className={cfg.className}>{cfg.label}</Badge>;
}

const ORDER_STATUS_VARIANT: Record<string, { variant: "warning" | "default" | "success" | "destructive"; label: string }> = {
  pending: { variant: "warning", label: "Pending" },
  payment_received: { variant: "default", label: "Payment Received" },
  processing: { variant: "warning", label: "Processing" },
  delivered: { variant: "success", label: "Delivered" },
  cancelled: { variant: "destructive", label: "Cancelled" },
};

function OrderStatusBadge({ status }: { status: string }) {
  const cfg = ORDER_STATUS_VARIANT[status] ?? { variant: "outline" as const, label: status };
  if (status === "processing") {
    return <Badge className="border-transparent bg-orange-600 text-white">{cfg.label}</Badge>;
  }
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

const PLAN_COLORS: Record<string, string> = {
  starter: "bg-gray-600 text-white",
  growth: "bg-blue-600 text-white",
  premium: "bg-purple-600 text-white",
  enterprise: "bg-amber-600 text-white",
};

function PlanBadge({ plan }: { plan: string }) {
  return (
    <Badge className={PLAN_COLORS[plan] ?? ""}>
      {plan.charAt(0).toUpperCase() + plan.slice(1)}
    </Badge>
  );
}

function SubStatusBadge({ status }: { status: string }) {
  switch (status) {
    case "active":
      return <Badge variant="success">Active</Badge>;
    case "paused":
      return <Badge variant="warning">Paused</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

/* ---------- pipeline visualization ---------- */

const PIPELINE_STEPS = [
  { key: "pending", label: "Pending", icon: Clock },
  { key: "payment_received", label: "Payment", icon: CreditCard },
  { key: "processing", label: "Processing", icon: Package },
  { key: "delivered", label: "Delivered", icon: CheckCircle },
] as const;

function statusIndex(status: string): number {
  return PIPELINE_STEPS.findIndex((s) => s.key === status);
}

function OrderPipeline({ status }: { status: string }) {
  const current = statusIndex(status);
  const isCancelled = status === "cancelled";

  return (
    <div className="flex items-center gap-1 sm:gap-2">
      {PIPELINE_STEPS.map((step, i) => {
        const Icon = step.icon;
        const isActive = !isCancelled && i <= current;
        const isCurrent = !isCancelled && i === current;

        return (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <ArrowRight
                className={`hidden h-4 w-4 flex-shrink-0 sm:block ${
                  isActive ? "text-blue-400" : "text-gray-700"
                }`}
              />
            )}
            <div
              className={`flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium ${
                isCurrent
                  ? "bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/40"
                  : isActive
                    ? "text-green-400"
                    : "text-gray-600"
              }`}
            >
              <Icon className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="hidden sm:inline">{step.label}</span>
            </div>
          </React.Fragment>
        );
      })}
      {isCancelled && (
        <>
          <ArrowRight className="hidden h-4 w-4 flex-shrink-0 text-gray-700 sm:block" />
          <div className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-2 py-1 text-xs font-medium text-red-400 ring-1 ring-red-500/40">
            <XCircle className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="hidden sm:inline">Cancelled</span>
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- status filter tabs ---------- */

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "payment_received", label: "Payment Received" },
  { value: "processing", label: "Processing" },
  { value: "delivered", label: "Delivered" },
  { value: "cancelled", label: "Cancelled" },
] as const;

/* ---------- main page ---------- */

export default function OrdersPage() {
  const { data: session } = useSession();
  const token = useApiToken();
  const clientId = (session?.user as any)?.clientId;

  const { data: orders, loading: ordersLoading, error: ordersError, refetch: refetchOrders } =
    useApi<Order[]>(clientId ? `/orders?skip=0&limit=50` : null);

  const { data: subscriptions, loading: subsLoading, error: subsError } =
    useApi<Subscription[]>(clientId ? `/orders/subscriptions` : null);

  const [statusFilter, setStatusFilter] = useState("all");
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const filteredOrders = useMemo(() => {
    const list = orders || [];
    if (statusFilter === "all") return list;
    return list.filter((o) => o.status === statusFilter);
  }, [orders, statusFilter]);

  /* cancel handler */
  const handleCancel = async (orderId: string) => {
    if (!confirm("Are you sure you want to cancel this order?")) return;
    setCancellingId(orderId);
    try {
      await apiFetch(`/orders/${orderId}`, token, {
        method: "PUT",
        body: JSON.stringify({ status: "cancelled" }),
      });
      refetchOrders();
    } catch {
      alert("Failed to cancel order. Please try again.");
    } finally {
      setCancellingId(null);
    }
  };

  /* loading / error states */
  const loading = ordersLoading || subsLoading;
  const error = ordersError || subsError;

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
        <p className="text-lg text-red-400">Failed to load data</p>
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Orders & Subscriptions</h1>
        <p className="text-gray-400">Track your orders and manage subscriptions</p>
      </div>

      {/* top-level tabs */}
      <Tabs defaultValue="orders">
        <TabsList>
          <TabsTrigger value="orders">Orders</TabsTrigger>
          <TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
        </TabsList>

        {/* ========== ORDERS TAB ========== */}
        <TabsContent value="orders">
          <div className="space-y-4">
            {/* status filter pills */}
            <div className="flex flex-wrap gap-2">
              {STATUS_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setStatusFilter(f.value)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    statusFilter === f.value
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* order cards */}
            {filteredOrders.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Package className="mb-3 h-12 w-12 text-gray-600" />
                  <p className="text-lg font-medium text-gray-400">No orders yet</p>
                  <p className="text-sm text-gray-500">
                    Your orders will appear here once you place one.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filteredOrders.map((order) => (
                  <Card key={order.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <OrderTypeBadge type={order.order_type} />
                          <OrderStatusBadge status={order.status} />
                        </div>
                        <span className="text-xs text-gray-500">
                          {formatDate(order.created_at)}
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {/* pipeline */}
                      <OrderPipeline status={order.status} />

                      {/* details */}
                      <div className="space-y-1.5 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-gray-400">Amount</span>
                          <span className="font-semibold text-white">
                            {formatCurrency(order.amount)}{" "}
                            <span className="text-xs text-gray-500">
                              {order.currency?.toUpperCase()}
                            </span>
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-gray-400">Order ID</span>
                          <span className="font-mono text-xs text-gray-500">
                            {order.id.slice(0, 8)}…
                          </span>
                        </div>
                        {order.delivered_at && (
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400">Delivered</span>
                            <span className="text-green-400">
                              {formatDate(order.delivered_at)}
                            </span>
                          </div>
                        )}
                        {order.notes && (
                          <p className="truncate text-xs text-gray-500">{order.notes}</p>
                        )}
                      </div>

                      {/* cancel button */}
                      {order.status === "pending" && (
                        <Button
                          variant="destructive"
                          size="sm"
                          className="w-full"
                          disabled={cancellingId === order.id}
                          onClick={() => handleCancel(order.id)}
                        >
                          {cancellingId === order.id ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <XCircle className="mr-2 h-4 w-4" />
                          )}
                          Cancel Order
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* ========== SUBSCRIPTIONS TAB ========== */}
        <TabsContent value="subscriptions">
          {(subscriptions || []).length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-16">
                <CreditCard className="mb-3 h-12 w-12 text-gray-600" />
                <p className="text-lg font-medium text-gray-400">No active subscriptions</p>
                <p className="text-sm text-gray-500">
                  Subscribe to a plan to get started with AdFlux.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {(subscriptions || []).map((sub) => (
                <Card key={sub.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <PlanBadge plan={sub.plan} />
                      <SubStatusBadge status={sub.status} />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* price */}
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-bold text-white">
                        {formatCurrency(sub.price)}
                      </span>
                      <span className="text-sm text-gray-500">
                        / {sub.interval === "yearly" ? "year" : "month"}
                      </span>
                    </div>

                    {/* details */}
                    <div className="space-y-1.5 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-400">Started</span>
                        <span className="text-gray-300">{formatDate(sub.started_at)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-400">Next billing</span>
                        <span className="text-gray-300">{formatDate(sub.next_billing_at)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-400">Currency</span>
                        <span className="text-xs text-gray-500">
                          {sub.currency?.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
