"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  MessageCircle,
  Search,
  Send,
  Loader2,
  User,
  Clock,
  Filter,
  UserPlus,
} from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { cn } from "@/lib/utils"

type Conversation = {
  id: string
  client_id: string | null
  client_name: string | null
  status: string
  subject: string
  assigned_admin: string | null
  last_message: string | null
  last_message_time: string | null
  created_at: string
}

type Message = {
  id: string
  session_id: string
  sender: string
  text: string
  created_at: string
}

type ConversationDetail = Conversation & {
  messages: Message[]
}

type TeamMember = {
  id: string
  name: string
  email: string
  role: string
}

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "open", label: "Open" },
  { value: "ai", label: "Pending (AI)" },
  { value: "escalated", label: "Escalated" },
  { value: "closed", label: "Closed" },
]

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "—"
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return "just now"
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function statusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    open: { className: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", label: "Open" },
    ai: { className: "bg-blue-500/10 text-blue-400 border-blue-500/20", label: "AI" },
    escalated: { className: "bg-amber-500/10 text-amber-400 border-amber-500/20", label: "Escalated" },
    closed: { className: "bg-gray-500/10 text-gray-400 border-gray-500/20", label: "Closed" },
  }
  const info = map[status] || map.open
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-medium", info.className)}>
      {info.label}
    </span>
  )
}

export default function ChatPage() {
  const token = useApiToken()
  const { data: team } = useApi<TeamMember[]>("/admin/users")

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selected, setSelected] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [msgLoading, setMsgLoading] = useState(false)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [showAssign, setShowAssign] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  // Fetch conversations
  const fetchConversations = useCallback(async () => {
    if (!token) return
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set("status", statusFilter)
      params.set("limit", "100")
      const data = await apiFetch<Conversation[]>(`/chat/conversations?${params}`, token)
      setConversations(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [token, statusFilter])

  useEffect(() => {
    setLoading(true)
    fetchConversations()
    const interval = setInterval(fetchConversations, 15_000)
    return () => clearInterval(interval)
  }, [fetchConversations])

  // Load selected conversation
  const loadConversation = async (id: string) => {
    if (!token) return
    setMsgLoading(true)
    try {
      const data = await apiFetch<ConversationDetail>(`/chat/conversations/${id}`, token)
      setSelected(data)
    } catch {
      // ignore
    } finally {
      setMsgLoading(false)
    }
  }

  // Poll messages for selected conversation
  useEffect(() => {
    if (!selected || !token) return
    const poll = async () => {
      try {
        const data = await apiFetch<ConversationDetail>(`/chat/conversations/${selected.id}`, token)
        setSelected(data)
      } catch {
        // ignore
      }
    }
    pollRef.current = setInterval(poll, 5_000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [selected?.id, token]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    scrollToBottom()
  }, [selected?.messages, scrollToBottom])

  // Send message
  const sendMessage = async () => {
    if (!input.trim() || !selected || !token || sending) return
    const text = input.trim()
    setInput("")
    setSending(true)
    try {
      await apiFetch(`/chat/conversations/${selected.id}/messages`, token, {
        method: "POST",
        body: JSON.stringify({ text }),
      })
      // Refresh messages
      const data = await apiFetch<ConversationDetail>(`/chat/conversations/${selected.id}`, token)
      setSelected(data)
    } catch {
      setInput(text)
    } finally {
      setSending(false)
    }
  }

  // Close conversation
  const closeConversation = async () => {
    if (!selected || !token) return
    try {
      await apiFetch(`/chat/conversations/${selected.id}/close`, token, { method: "PUT" })
      fetchConversations()
      const data = await apiFetch<ConversationDetail>(`/chat/conversations/${selected.id}`, token)
      setSelected(data)
    } catch {
      // ignore
    }
  }

  // Assign conversation
  const assignConversation = async (adminId: string) => {
    if (!selected || !token) return
    try {
      await apiFetch(`/chat/conversations/${selected.id}/assign`, token, {
        method: "PUT",
        body: JSON.stringify({ admin_id: adminId }),
      })
      setShowAssign(false)
      fetchConversations()
      const data = await apiFetch<ConversationDetail>(`/chat/conversations/${selected.id}`, token)
      setSelected(data)
    } catch {
      // ignore
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const filtered = conversations.filter((c) => {
    if (search) {
      const q = search.toLowerCase()
      const matchName = c.client_name?.toLowerCase().includes(q)
      const matchMsg = c.last_message?.toLowerCase().includes(q)
      const matchSubject = c.subject?.toLowerCase().includes(q)
      if (!matchName && !matchMsg && !matchSubject) return false
    }
    return true
  })

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      {/* Left panel — conversation list */}
      <Card className="flex w-80 flex-col overflow-hidden lg:w-96">
        <div className="border-b border-border p-4">
          <h2 className="mb-3 text-lg font-semibold">Chat Support</h2>
          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search conversations…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          {/* Status filter */}
          <div className="flex flex-wrap gap-1.5">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setStatusFilter(opt.value)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  statusFilter === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
              <MessageCircle className="h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No conversations found</p>
            </div>
          ) : (
            filtered.map((conv) => (
              <button
                key={conv.id}
                onClick={() => loadConversation(conv.id)}
                className={cn(
                  "flex w-full flex-col gap-1 border-b border-border px-4 py-3 text-left transition-colors hover:bg-secondary/50",
                  selected?.id === conv.id && "bg-secondary"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 truncate">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                      <User className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <span className="truncate text-sm font-medium">
                      {conv.client_name || "Unknown Client"}
                    </span>
                  </div>
                  {statusBadge(conv.status)}
                </div>
                {conv.last_message && (
                  <p className="truncate pl-10 text-xs text-muted-foreground">
                    {conv.last_message}
                  </p>
                )}
                <div className="flex items-center gap-1 pl-10">
                  <Clock className="h-3 w-3 text-muted-foreground/60" />
                  <span className="text-xs text-muted-foreground/60">
                    {timeAgo(conv.last_message_time || conv.created_at)}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      </Card>

      {/* Right panel — messages */}
      <Card className="flex flex-1 flex-col overflow-hidden">
        {!selected ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <MessageCircle className="h-12 w-12 text-muted-foreground/30" />
            <p className="text-muted-foreground">Select a conversation to view messages</p>
          </div>
        ) : (
          <>
            {/* Conversation header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div>
                <h3 className="font-semibold">{selected.client_name || "Unknown Client"}</h3>
                <p className="text-xs text-muted-foreground">{selected.subject}</p>
              </div>
              <div className="flex items-center gap-2">
                {/* Assign dropdown */}
                <div className="relative">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAssign(!showAssign)}
                  >
                    <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                    Assign
                  </Button>
                  {showAssign && (
                    <div className="absolute right-0 top-full z-10 mt-1 w-56 rounded-lg border border-border bg-card p-1 shadow-lg">
                      {(team || []).map((member) => (
                        <button
                          key={member.id}
                          onClick={() => assignConversation(member.id)}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-secondary",
                            selected.assigned_admin === member.id && "bg-primary/10 text-primary"
                          )}
                        >
                          <User className="h-3.5 w-3.5" />
                          <span>{member.name}</span>
                          <span className="ml-auto text-xs text-muted-foreground">{member.role}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {selected.status !== "closed" ? (
                  <Button variant="outline" size="sm" onClick={closeConversation}>
                    Close
                  </Button>
                ) : (
                  <Badge variant="secondary">Closed</Badge>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
              {msgLoading ? (
                <div className="flex flex-1 items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (selected.messages || []).length === 0 ? (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-sm text-muted-foreground">No messages yet</p>
                </div>
              ) : (
                (selected.messages || []).map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      "flex",
                      msg.sender === "user" ? "justify-start" : "justify-end"
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-[70%] rounded-2xl px-4 py-2.5 text-sm",
                        msg.sender === "user"
                          ? "rounded-bl-md bg-secondary text-foreground"
                          : msg.sender === "admin"
                          ? "rounded-br-md bg-primary text-primary-foreground"
                          : "rounded-br-md bg-accent/20 text-foreground"
                      )}
                    >
                      <p className="mb-0.5 text-xs font-medium opacity-70">
                        {msg.sender === "user"
                          ? "Client"
                          : msg.sender === "admin"
                          ? "Admin"
                          : "AI Assistant"}
                      </p>
                      <p className="whitespace-pre-wrap">{msg.text}</p>
                      <p className="mt-1 text-right text-[10px] opacity-50">
                        {timeAgo(msg.created_at)}
                      </p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Reply input */}
            {selected.status !== "closed" && (
              <div className="border-t border-border p-3">
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Type your reply…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={sending}
                  />
                  <Button onClick={sendMessage} disabled={!input.trim() || sending} size="sm">
                    {sending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
