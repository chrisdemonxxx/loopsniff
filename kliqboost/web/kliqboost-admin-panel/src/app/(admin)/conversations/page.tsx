"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  MessageCircle,
  Search,
  Users,
  Bot,
  ArrowLeft,
  Loader2,
  RefreshCw,
  Send,
  Clock,
} from "lucide-react"
import { useApi } from "@/lib/api"
import { cn } from "@/lib/utils"

// --- Types ---

type Conversation = {
  username: string
  status: string
  source: string
  contacted_by: string | null
  bant_score: number
  notes: string | null
  contacted_at: string | null
  message_count: number
  last_message_at: string | null
  last_message_preview: string | null
}

type Message = {
  id: number
  lead_username: string
  account_phone: string
  direction: string
  text: string
  sent_at: string
  template_id: string | null
}

type MessagesResponse = {
  lead: Conversation
  messages: Message[]
  total: number
}

// --- Helpers ---

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "—"
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const seconds = Math.floor((now - then) / 1000)
  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatMessageTime(dateStr: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(dateStr))
}

function bantVariant(score: number): "destructive" | "warning" | "success" {
  if (score <= 3) return "destructive"
  if (score <= 6) return "warning"
  return "success"
}

const STATUS_TABS = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
] as const

// --- Component ---

export default function ConversationsPage() {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [selectedUsername, setSelectedUsername] = useState<string | null>(null)
  const [mobileShowChat, setMobileShowChat] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Build conversations API path
  const params = new URLSearchParams({ limit: "50", skip: "0" })
  if (statusFilter !== "all") params.set("status", statusFilter)
  if (search.trim()) params.set("q", search.trim())

  const {
    data: conversations,
    loading: convsLoading,
    error: convsError,
    refetch: refetchConvs,
  } = useApi<Conversation[]>(`/outreach/sqlite/conversations?${params.toString()}`)

  const {
    data: activeData,
    refetch: refetchActive,
  } = useApi<Conversation[]>("/outreach/sqlite/conversations/active?hours=24")

  const {
    data: messagesData,
    loading: msgsLoading,
    refetch: refetchMsgs,
  } = useApi<MessagesResponse>(
    selectedUsername
      ? `/outreach/sqlite/conversations/${encodeURIComponent(selectedUsername)}/messages`
      : null
  )

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetchConvs()
      refetchActive()
      if (selectedUsername) refetchMsgs()
    }, 10_000)
    return () => clearInterval(interval)
  }, [refetchConvs, refetchActive, refetchMsgs, selectedUsername])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messagesData?.messages])

  const list = conversations ?? []
  const activeCount = activeData?.length ?? 0

  const handleSelectConversation = (username: string) => {
    setSelectedUsername(username)
    setMobileShowChat(true)
  }

  const handleBack = () => {
    setMobileShowChat(false)
    setSelectedUsername(null)
  }

  const handleRefresh = () => {
    refetchConvs()
    refetchActive()
    if (selectedUsername) refetchMsgs()
  }

  // Selected conversation metadata
  const selectedConv =
    messagesData?.lead ?? list.find((c) => c.username === selectedUsername)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Live Conversations</h1>
          <Badge variant="success" className="gap-1">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            {activeCount} active
          </Badge>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} className="gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {/* Two-panel layout */}
      <Card className="overflow-hidden">
        <div className="flex h-[calc(100vh-12rem)] min-h-[500px]">
          {/* Left panel — Conversation List */}
          <div
            className={cn(
              "w-full md:w-[340px] lg:w-[380px] border-r border-border flex flex-col shrink-0",
              mobileShowChat && "hidden md:flex"
            )}
          >
            {/* Search + Tabs */}
            <div className="p-3 space-y-3 border-b border-border">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search conversations..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex gap-1">
                {STATUS_TABS.map((tab) => (
                  <button
                    key={tab.value}
                    onClick={() => setStatusFilter(tab.value)}
                    className={cn(
                      "px-3 py-1 rounded-md text-xs font-medium transition-colors",
                      statusFilter === tab.value
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Conversation items */}
            <div className="flex-1 overflow-y-auto">
              {convsLoading && list.length === 0 ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : convsError ? (
                <div className="text-center py-12 px-4">
                  <p className="text-destructive text-sm mb-2">Failed to load</p>
                  <p className="text-xs text-muted-foreground mb-3">{convsError}</p>
                  <Button variant="outline" size="sm" onClick={refetchConvs}>
                    Retry
                  </Button>
                </div>
              ) : list.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
                  <MessageCircle className="h-10 w-10 text-muted-foreground/40 mb-3" />
                  <p className="text-sm font-medium text-muted-foreground">
                    No conversations yet
                  </p>
                  <p className="text-xs text-muted-foreground/60 mt-1">
                    Conversations will appear here when leads are contacted
                  </p>
                </div>
              ) : (
                list.map((conv) => (
                  <button
                    key={conv.username}
                    onClick={() => handleSelectConversation(conv.username)}
                    className={cn(
                      "w-full text-left px-4 py-3 border-b border-border transition-colors hover:bg-secondary/50",
                      selectedUsername === conv.username && "bg-secondary/80"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary shrink-0">
                          <Users className="h-4 w-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium truncate">
                              {conv.username}
                            </span>
                            <Badge
                              variant={bantVariant(conv.bant_score ?? 0)}
                              className="text-[10px] px-1.5 py-0"
                            >
                              {conv.bant_score ?? 0}
                            </Badge>
                          </div>
                          {conv.contacted_by && (
                            <span className="text-[10px] text-muted-foreground/60 truncate block">
                              via {conv.contacted_by}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end shrink-0 gap-0.5">
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                          {timeAgo(conv.last_message_at)}
                        </span>
                        {conv.message_count > 0 && (
                          <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                            <MessageCircle className="h-2.5 w-2.5" />
                            {conv.message_count}
                          </span>
                        )}
                      </div>
                    </div>
                    {conv.last_message_preview && (
                      <p className="text-xs text-muted-foreground mt-1.5 line-clamp-1 pl-10">
                        {conv.last_message_preview}
                      </p>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Right panel — Message Thread */}
          <div
            className={cn(
              "flex-1 flex flex-col min-w-0",
              !mobileShowChat && "hidden md:flex"
            )}
          >
            {!selectedUsername ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-secondary mb-4">
                  <MessageCircle className="h-8 w-8 text-muted-foreground/40" />
                </div>
                <p className="text-sm font-medium text-muted-foreground">
                  Select a conversation
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Choose a conversation from the list to view messages
                </p>
              </div>
            ) : (
              <>
                {/* Lead info header */}
                <div className="px-4 py-3 border-b border-border bg-card/50">
                  <div className="flex items-center gap-3">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="md:hidden h-8 w-8"
                      onClick={handleBack}
                    >
                      <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary shrink-0">
                      <Users className="h-4.5 w-4.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm">
                          {selectedConv?.username ?? selectedUsername}
                        </span>
                        {selectedConv && (
                          <>
                            <Badge
                              variant={bantVariant(selectedConv.bant_score ?? 0)}
                              className="text-[10px] px-1.5 py-0"
                            >
                              BANT {selectedConv.bant_score ?? 0}
                            </Badge>
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                              {selectedConv.status}
                            </Badge>
                          </>
                        )}
                      </div>
                      {selectedConv && (
                        <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-0.5">
                          {selectedConv.source && <span>Source: {selectedConv.source}</span>}
                          {selectedConv.contacted_by && (
                            <span>Account: {selectedConv.contacted_by}</span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5">
                      {messagesData && (
                        <span className="text-[10px] text-muted-foreground">
                          {messagesData.total} messages
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                  {msgsLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                  ) : messagesData?.messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                      <Send className="h-8 w-8 text-muted-foreground/30 mb-2" />
                      <p className="text-sm text-muted-foreground">No messages yet</p>
                    </div>
                  ) : (
                    <>
                      {messagesData?.messages.map((msg) => {
                        const isOutgoing = msg.direction === "outbound"
                        return (
                          <div
                            key={msg.id}
                            className={cn(
                              "flex",
                              isOutgoing ? "justify-end" : "justify-start"
                            )}
                          >
                            <div
                              className={cn(
                                "max-w-[75%] rounded-2xl px-4 py-2.5 shadow-sm",
                                isOutgoing
                                  ? "bg-blue-600 text-white rounded-br-md"
                                  : "bg-secondary text-foreground rounded-bl-md"
                              )}
                            >
                              <p className="text-sm whitespace-pre-wrap break-words">
                                {msg.text}
                              </p>
                              <div
                                className={cn(
                                  "flex items-center gap-2 mt-1.5",
                                  isOutgoing ? "justify-end" : "justify-start"
                                )}
                              >
                                {msg.template_id && (
                                  <Badge
                                    variant={isOutgoing ? "info" : "secondary"}
                                    className="text-[9px] px-1.5 py-0"
                                  >
                                    <Bot className="h-2.5 w-2.5 mr-0.5" />
                                    {msg.template_id}
                                  </Badge>
                                )}
                                <span
                                  className={cn(
                                    "text-[10px] flex items-center gap-1",
                                    isOutgoing
                                      ? "text-blue-200"
                                      : "text-muted-foreground"
                                  )}
                                >
                                  <Clock className="h-2.5 w-2.5" />
                                  {formatMessageTime(msg.sent_at)}
                                </span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                      <div ref={messagesEndRef} />
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  )
}
