"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import {
  Search,
  ExternalLink,
  Loader2,
  Ticket,
  Clock,
  CheckCircle2,
  AlertCircle,
  MessageSquare,
  Headphones,
  CreditCard,
  Settings,
  HelpCircle,
  ShieldAlert,
  Trash2,
} from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { useToast } from "@/components/ui/toast"
import { formatDate, cn } from "@/lib/utils"

type TicketStatus = "open" | "in_progress" | "awaiting_client" | "resolved" | "closed"
type TicketPriority = "urgent" | "high" | "medium" | "low"
type TicketCategory = "billing" | "technical" | "account" | "general" | "security"

interface TicketItem {
  id: string
  client_id: string
  subject: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  assigned_admin: string | null
  created_by_type: string
  message_count: number
  created_at: string
  updated_at: string
}

interface TicketStats {
  by_status: Record<string, number>
  by_priority: Record<string, number>
  by_category: Record<string, number>
}

const priorityVariant: Record<TicketPriority, string> = {
  urgent: "destructive",
  high: "warning",
  medium: "secondary",
  low: "outline",
}

const statusVariant: Record<TicketStatus, string> = {
  open: "info",
  in_progress: "warning",
  awaiting_client: "default",
  resolved: "success",
  closed: "secondary",
}

const statusLabel: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  awaiting_client: "Awaiting Client",
  resolved: "Resolved",
  closed: "Closed",
}

const categoryIcons: Record<TicketCategory, React.ReactNode> = {
  billing: <CreditCard className="h-3 w-3 mr-1 inline" />,
  technical: <Settings className="h-3 w-3 mr-1 inline" />,
  account: <Headphones className="h-3 w-3 mr-1 inline" />,
  general: <HelpCircle className="h-3 w-3 mr-1 inline" />,
  security: <ShieldAlert className="h-3 w-3 mr-1 inline" />,
}

export default function TicketsPage() {
  const router = useRouter()
  const token = useApiToken()
  const { toast } = useToast()
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [priorityFilter, setPriorityFilter] = useState<string>("all")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [search, setSearch] = useState("")
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const queryParams = new URLSearchParams()
  if (statusFilter !== "all") queryParams.set("status", statusFilter)
  if (priorityFilter !== "all") queryParams.set("priority", priorityFilter)
  if (categoryFilter !== "all") queryParams.set("category", categoryFilter)
  if (search.trim()) queryParams.set("q", search.trim())
  queryParams.set("skip", "0")
  queryParams.set("limit", "50")

  const queryString = queryParams.toString()
  const { data: tickets, loading, error, refetch } = useApi<TicketItem[]>(
    `/tickets?${queryString}`
  )
  const { data: stats } = useApi<TicketStats>("/tickets/stats")

  const openCount = stats?.by_status?.open ?? 0
  const inProgressCount = stats?.by_status?.in_progress ?? 0
  const resolvedCount = stats?.by_status?.resolved ?? 0
  const totalCount = Object.values(stats?.by_status ?? {}).reduce((a, b) => a + b, 0)

  const handleDelete = async (e: React.MouseEvent, ticketId: string, subject: string) => {
    e.stopPropagation()
    if (!token) return
    if (!confirm(`Delete ticket "${subject}"? This cannot be undone.`)) return
    setDeletingId(ticketId)
    try {
      await apiFetch(`/tickets/${ticketId}`, token, { method: "DELETE" })
      toast("Ticket deleted", "success")
      refetch()
    } catch (err: any) {
      toast(err?.message || "Delete failed", "error")
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading tickets…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load tickets: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Support Tickets</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-blue-400" />
              <span className="text-xs text-muted-foreground">Open</span>
            </div>
            <span className="text-xl font-bold">{openCount}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              <span className="text-xs text-muted-foreground">In Progress</span>
            </div>
            <span className="text-xl font-bold">{inProgressCount}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-xs text-muted-foreground">Resolved</span>
            </div>
            <span className="text-xl font-bold">{resolvedCount}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <Ticket className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Total</span>
            </div>
            <span className="text-xl font-bold">{totalCount}</span>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4">
            {/* Status Filter Tabs */}
            <div className="inline-flex h-9 items-center justify-center rounded-lg bg-secondary p-1 flex-wrap">
              {(
                [
                  { value: "all", label: "All" },
                  { value: "open", label: "Open" },
                  { value: "in_progress", label: "In Progress" },
                  { value: "awaiting_client", label: "Awaiting Client" },
                  { value: "resolved", label: "Resolved" },
                  { value: "closed", label: "Closed" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  className={cn(
                    "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all",
                    statusFilter === tab.value
                      ? "bg-card text-foreground shadow"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                  onClick={() => setStatusFilter(tab.value)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Filters Row */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search tickets..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                options={[
                  { value: "all", label: "All Priorities" },
                  { value: "urgent", label: "Urgent" },
                  { value: "high", label: "High" },
                  { value: "medium", label: "Medium" },
                  { value: "low", label: "Low" },
                ]}
                className="w-40"
              />
              <Select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                options={[
                  { value: "all", label: "All Categories" },
                  { value: "billing", label: "Billing" },
                  { value: "technical", label: "Technical" },
                  { value: "account", label: "Account" },
                  { value: "general", label: "General" },
                  { value: "security", label: "Security" },
                ]}
                className="w-40"
              />
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Subject</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Messages</TableHead>
                <TableHead>Created</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(tickets ?? []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No tickets found
                  </TableCell>
                </TableRow>
              ) : (
                (tickets ?? []).map((ticket) => (
                  <TableRow
                    key={ticket.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/tickets/${ticket.id}`)}
                  >
                    <TableCell className="font-medium max-w-xs truncate">
                      {ticket.subject}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {categoryIcons[ticket.category]}
                        {ticket.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={priorityVariant[ticket.priority] as any}>
                        {ticket.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[ticket.status] as any}>
                        {statusLabel[ticket.status] ?? ticket.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-muted-foreground text-sm">
                        <MessageSquare className="h-3 w-3" />
                        {ticket.message_count}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {formatDate(ticket.created_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Link href={`/tickets/${ticket.id}`} onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" title="Open">
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Delete ticket"
                          disabled={deletingId === ticket.id}
                          onClick={(e) => handleDelete(e, ticket.id, ticket.subject)}
                        >
                          {deletingId === ticket.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4 text-red-400" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
