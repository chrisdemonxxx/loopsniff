"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Loader2,
  Ticket,
  MessageSquare,
  Calendar,
  X,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi, useApiToken, apiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

interface TicketItem {
  id: string;
  subject: string;
  status: string;
  priority: string;
  category: string;
  message_count?: number;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  open: "bg-[#3b82f6]",
  in_progress: "bg-[#f59e0b]",
  awaiting_client: "bg-[#a855f7]",
  resolved: "bg-[#10b981]",
  closed: "bg-[#6b7280]",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  awaiting_client: "Awaiting Client",
  resolved: "Resolved",
  closed: "Closed",
};

const PRIORITY_VARIANT: Record<string, "secondary" | "default" | "warning" | "destructive"> = {
  low: "secondary",
  medium: "default",
  high: "warning",
  urgent: "destructive",
};

const CATEGORY_COLORS: Record<string, string> = {
  billing: "bg-blue-600/20 text-blue-400 border-blue-800",
  technical: "bg-orange-600/20 text-orange-400 border-orange-800",
  account: "bg-purple-600/20 text-purple-400 border-purple-800",
  general: "bg-gray-600/20 text-gray-400 border-gray-700",
};

const STATUS_TABS = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "awaiting_client", label: "Awaiting Client" },
  { value: "resolved", label: "Resolved" },
];

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(date));
}

export default function TicketsPage() {
  const router = useRouter();
  const token = useApiToken();

  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);

  const apiPath =
    statusFilter === "all"
      ? "/tickets?skip=0&limit=50"
      : `/tickets?status=${statusFilter}&skip=0&limit=50`;

  const { data: tickets, loading, refetch } = useApi<TicketItem[]>(apiPath);
  const { toast } = useToast();

  // Create form state
  const [subject, setSubject] = useState("");
  const [category, setCategory] = useState("general");
  const [priority, setPriority] = useState("medium");
  const [message, setMessage] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !subject.trim() || !message.trim()) return;
    setCreating(true);
    try {
      await apiFetch("/tickets", token, {
        method: "POST",
        body: JSON.stringify({ subject, category, priority, message }),
      });
      setShowCreate(false);
      setSubject("");
      setCategory("general");
      setPriority("medium");
      setMessage("");
      refetch();
    } catch (err: any) {
      toast(err.message || "Failed to create ticket. Please try again.", "error");
    } finally {
      setCreating(false);
    }
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Support Tickets</h1>
          <p className="text-gray-400">Track and manage your support requests</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Ticket
        </Button>
      </div>

      {/* Status filter tabs */}
      <Tabs value={statusFilter} onValueChange={setStatusFilter}>
        <TabsList>
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Tickets list */}
      {!tickets || tickets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Ticket className="h-12 w-12 text-gray-700" />
          <p className="mt-3 text-gray-400">No tickets found</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => setShowCreate(true)}
          >
            <Plus className="mr-2 h-4 w-4" />
            Create your first ticket
          </Button>
        </div>
      ) : (
        <div className="grid gap-3">
          {tickets.map((ticket) => (
            <Card
              key={ticket.id}
              className="cursor-pointer transition-colors hover:bg-gray-800/50"
              onClick={() => router.push(`/tickets/${ticket.id}`)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-medium text-white truncate">
                      {ticket.subject}
                    </h3>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {/* Status badge */}
                      <Badge
                        className={cn(
                          "border-transparent text-white",
                          STATUS_COLORS[ticket.status] || STATUS_COLORS.open
                        )}
                      >
                        {STATUS_LABELS[ticket.status] || ticket.status}
                      </Badge>
                      {/* Priority badge */}
                      <Badge variant={PRIORITY_VARIANT[ticket.priority] || "default"}>
                        {ticket.priority}
                      </Badge>
                      {/* Category badge */}
                      <Badge
                        variant="outline"
                        className={cn(
                          CATEGORY_COLORS[ticket.category] || CATEGORY_COLORS.general
                        )}
                      >
                        {ticket.category}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {formatDate(ticket.created_at)}
                    </span>
                    {ticket.message_count != null && (
                      <span className="flex items-center gap-1">
                        <MessageSquare className="h-3 w-3" />
                        {ticket.message_count}
                      </span>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Ticket Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-xl border border-gray-800 bg-gray-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
              <h2 className="text-lg font-semibold text-white">New Ticket</h2>
              <button
                onClick={() => setShowCreate(false)}
                className="rounded-md p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4 px-6 py-4">
              <div className="space-y-2">
                <Label htmlFor="subject">Subject</Label>
                <Input
                  id="subject"
                  placeholder="Brief description of your issue"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select value={category} onValueChange={setCategory}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="billing">Billing</SelectItem>
                      <SelectItem value="technical">Technical</SelectItem>
                      <SelectItem value="account">Account</SelectItem>
                      <SelectItem value="general">General</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select value={priority} onValueChange={setPriority}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="message">Message</Label>
                <textarea
                  id="message"
                  rows={4}
                  placeholder="Describe your issue in detail..."
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  required
                  className="flex w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 border-t border-gray-800 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreate(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={creating || !subject.trim() || !message.trim()}>
                  {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Ticket
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
