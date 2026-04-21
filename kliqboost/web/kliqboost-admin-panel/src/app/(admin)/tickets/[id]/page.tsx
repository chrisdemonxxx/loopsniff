"use client"

import { use, useState, useRef, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { useToast } from "@/components/ui/toast"
import {
  ArrowLeft,
  Loader2,
  Send,
  Lock,
  User,
  Bot,
  Shield,
  MessageSquare,
  CreditCard,
  Settings,
  Headphones,
  HelpCircle,
  ShieldAlert,
  Trash2,
} from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatDate, formatDateTime, cn } from "@/lib/utils"

type TicketStatus = "open" | "in_progress" | "awaiting_client" | "resolved" | "closed"
type TicketPriority = "urgent" | "high" | "medium" | "low"
type TicketCategory = "billing" | "technical" | "account" | "general" | "security"

interface TicketMessage {
  id: string
  ticket_id: string
  sender_type: "client" | "admin" | "ai" | "system"
  sender_id: string | null
  text: string
  is_internal: boolean
  attachments: string[]
  created_at: string
}

interface TicketDetail {
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
  resolved_at: string | null
  messages: TicketMessage[]
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
  billing: <CreditCard className="h-3 w-3" />,
  technical: <Settings className="h-3 w-3" />,
  account: <Headphones className="h-3 w-3" />,
  general: <HelpCircle className="h-3 w-3" />,
  security: <ShieldAlert className="h-3 w-3" />,
}

const senderIcon: Record<string, React.ReactNode> = {
  client: <User className="h-4 w-4" />,
  admin: <Shield className="h-4 w-4" />,
  ai: <Bot className="h-4 w-4" />,
  system: <Settings className="h-4 w-4" />,
}

export default function TicketDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const token = useApiToken()
  const { toast } = useToast()
  const { data: ticket, loading, error, refetch } = useApi<TicketDetail>(`/tickets/${id}`)

  const [replyText, setReplyText] = useState("")
  const [isInternal, setIsInternal] = useState(false)
  const [sending, setSending] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [ticket?.messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !replyText.trim()) return
    setSending(true)
    setActionError(null)
    try {
      await apiFetch(`/tickets/${id}/messages`, token, {
        method: "POST",
        body: JSON.stringify({ text: replyText.trim(), is_internal: isInternal }),
      })
      setReplyText("")
      setIsInternal(false)
      refetch()
    } catch (err: any) {
      setActionError(err.message || "Failed to send message")
    } finally {
      setSending(false)
    }
  }

  const handleUpdate = async (data: Record<string, string>) => {
    if (!token) return
    setUpdating(true)
    setActionError(null)
    try {
      await apiFetch(`/tickets/${id}`, token, {
        method: "PUT",
        body: JSON.stringify(data),
      })
      refetch()
    } catch (err: any) {
      setActionError(err.message || "Failed to update ticket")
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async () => {
    if (!token || !ticket) return
    if (!confirm(`Delete ticket "${ticket.subject}"? This cannot be undone.`)) return
    setDeleting(true)
    setActionError(null)
    try {
      await apiFetch(`/tickets/${id}`, token, { method: "DELETE" })
      toast("Ticket deleted", "success")
      router.push("/tickets")
    } catch (err: any) {
      setActionError(err.message || "Failed to delete ticket")
      toast(err?.message || "Delete failed", "error")
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading ticket…</span>
      </div>
    )
  }

  if (error || !ticket) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-destructive">{error || "Ticket not found"}</p>
        <Link href="/tickets">
          <Button variant="outline">Back to Tickets</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Link href="/tickets">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-2xl font-bold flex-1 min-w-0 truncate">{ticket.subject}</h1>
        <Badge variant={statusVariant[ticket.status] as any}>
          {statusLabel[ticket.status]}
        </Badge>
        <Badge variant={priorityVariant[ticket.priority] as any}>
          {ticket.priority}
        </Badge>
        <Badge variant="secondary" className="flex items-center gap-1">
          {categoryIcons[ticket.category]}
          {ticket.category}
        </Badge>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleDelete}
          disabled={deleting}
          title="Delete ticket"
        >
          {deleting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4 text-red-400" />
          )}
        </Button>
      </div>

      {actionError && (
        <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">
          {actionError}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main: Message Thread */}
        <div className="flex-1 min-w-0 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Messages ({ticket.messages?.length ?? 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                {(ticket.messages ?? []).length === 0 ? (
                  <p className="text-center text-muted-foreground py-8 text-sm">
                    No messages yet
                  </p>
                ) : (
                  (ticket.messages ?? []).map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply Form */}
              <form onSubmit={handleSendMessage} className="mt-6 space-y-3 border-t border-border pt-4">
                <textarea
                  className="w-full min-h-[100px] rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
                  placeholder={isInternal ? "Write an internal note…" : "Type your reply…"}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                />
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={isInternal}
                      onChange={(e) => setIsInternal(e.target.checked)}
                      className="rounded border-border"
                    />
                    <Lock className="h-3 w-3" />
                    Internal Note
                  </label>
                  <Button type="submit" disabled={sending || !replyText.trim()}>
                    {sending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4 mr-2" />
                    )}
                    {isInternal ? "Add Note" : "Send Reply"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="w-full lg:w-[300px] space-y-4 shrink-0">
          {/* Ticket Metadata */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <span className="text-xs text-muted-foreground block">Client ID</span>
                <span className="text-sm font-mono">{ticket.client_id}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Assigned Admin</span>
                <span className="text-sm">{ticket.assigned_admin ?? "Unassigned"}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Created</span>
                <span className="text-sm">{formatDateTime(ticket.created_at)}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Updated</span>
                <span className="text-sm">{formatDateTime(ticket.updated_at)}</span>
              </div>
              {ticket.resolved_at && (
                <div>
                  <span className="text-xs text-muted-foreground block">Resolved</span>
                  <span className="text-sm">{formatDateTime(ticket.resolved_at)}</span>
                </div>
              )}
              <div>
                <span className="text-xs text-muted-foreground block">Created By</span>
                <span className="text-sm capitalize">{ticket.created_by_type}</span>
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground block mb-1.5">Status</label>
                <Select
                  value={ticket.status}
                  onChange={(e) => handleUpdate({ status: e.target.value })}
                  disabled={updating}
                  options={[
                    { value: "open", label: "Open" },
                    { value: "in_progress", label: "In Progress" },
                    { value: "awaiting_client", label: "Awaiting Client" },
                    { value: "resolved", label: "Resolved" },
                    { value: "closed", label: "Closed" },
                  ]}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1.5">Priority</label>
                <Select
                  value={ticket.priority}
                  onChange={(e) => handleUpdate({ priority: e.target.value })}
                  disabled={updating}
                  options={[
                    { value: "urgent", label: "Urgent" },
                    { value: "high", label: "High" },
                    { value: "medium", label: "Medium" },
                    { value: "low", label: "Low" },
                  ]}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1.5">Category</label>
                <Select
                  value={ticket.category}
                  onChange={(e) => handleUpdate({ category: e.target.value })}
                  disabled={updating}
                  options={[
                    { value: "billing", label: "Billing" },
                    { value: "technical", label: "Technical" },
                    { value: "account", label: "Account" },
                    { value: "general", label: "General" },
                    { value: "security", label: "Security" },
                  ]}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1.5">Assign Admin</label>
                <Input
                  placeholder="Admin username"
                  defaultValue={ticket.assigned_admin ?? ""}
                  onBlur={(e) => {
                    const value = e.target.value.trim()
                    if (value !== (ticket.assigned_admin ?? "")) {
                      handleUpdate({ assigned_admin: value })
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      handleUpdate({ assigned_admin: (e.target as HTMLInputElement).value.trim() })
                    }
                  }}
                  disabled={updating}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: TicketMessage }) {
  const isAdmin = message.sender_type === "admin"
  const isClient = message.sender_type === "client"
  const isAI = message.sender_type === "ai"

  if (message.is_internal) {
    return (
      <div className="mx-4">
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3">
          <div className="flex items-center gap-2 mb-1">
            <Lock className="h-3 w-3 text-amber-400" />
            <span className="text-xs font-semibold text-amber-400">Internal Note</span>
            <span className="text-xs text-muted-foreground ml-auto">
              {formatDateTime(message.created_at)}
            </span>
          </div>
          <p className="text-sm text-foreground whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("flex", isAdmin ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg p-3",
          isAdmin && "bg-blue-500/15 border border-blue-500/20",
          isClient && "bg-muted border border-border",
          isAI && "bg-purple-500/15 border border-purple-500/20",
          !isAdmin && !isClient && !isAI && "bg-muted border border-border"
        )}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className={cn(
            "flex items-center gap-1 text-xs font-semibold",
            isAdmin && "text-blue-400",
            isClient && "text-gray-400",
            isAI && "text-purple-400"
          )}>
            {senderIcon[message.sender_type] ?? senderIcon.system}
            {message.sender_type}
          </span>
          <span className="text-xs text-muted-foreground ml-auto">
            {formatDateTime(message.created_at)}
          </span>
        </div>
        <p className="text-sm text-foreground whitespace-pre-wrap">{message.text}</p>
        {message.attachments?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.attachments.map((att, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                📎 {att}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
