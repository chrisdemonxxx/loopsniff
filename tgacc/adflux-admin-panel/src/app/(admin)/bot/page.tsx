"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Search, Send, Flag, Tag, Loader2, AlertCircle, MessageSquare, ArrowLeft, X } from "lucide-react"
import { useApi, useApiToken, apiFetch, API_URL } from "@/lib/api"
import { useToast } from "@/components/ui/toast"
import { formatDateTime } from "@/lib/utils"
import { cn } from "@/lib/utils"

interface ChatSession {
  id: string
  client_id: string
  channel: string
  status: string
  assigned_admin: string | null
  created_at: string
  closed_at: string | null
}

interface ChatMessage {
  id: string
  session_id: string
  sender: string
  text: string
  metadata: any
  created_at: string
}

export default function BotPage() {
  const { data: sessions, loading: sessionsLoading, error: sessionsError } = useApi<ChatSession[]>("/chat/sessions")
  const token = useApiToken()

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [searchConv, setSearchConv] = useState("")
  const [replyText, setReplyText] = useState("")
  const [mobileShowList, setMobileShowList] = useState(true)
  const [tagInputOpen, setTagInputOpen] = useState(false)
  const [tagText, setTagText] = useState("")
  const [addingTag, setAddingTag] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { toast } = useToast()

  const selectedSession = sessions?.find(s => s.id === selectedSessionId) ?? null

  // Auto-select first session when loaded
  useEffect(() => {
    if (sessions?.length && !selectedSessionId) {
      setSelectedSessionId(sessions[0].id)
    }
  }, [sessions, selectedSessionId])

  // Fetch messages for selected session + poll every 5s
  const fetchMessages = useCallback(async () => {
    if (!selectedSessionId || !token) return
    try {
      const msgs = await apiFetch<ChatMessage[]>(
        `/chat/sessions/${selectedSessionId}/messages`,
        token,
      )
      setMessages(msgs)
    } catch {
      // silently fail on poll errors
    } finally {
      setMessagesLoading(false)
    }
  }, [selectedSessionId, token])

  useEffect(() => {
    if (!selectedSessionId || !token) return
    setMessagesLoading(true)
    setMessages([])
    fetchMessages()
    const interval = setInterval(fetchMessages, 5000)
    return () => clearInterval(interval)
  }, [selectedSessionId, token, fetchMessages])

  // Manage WebSocket for sending messages
  useEffect(() => {
    if (!selectedSessionId) return
    const wsUrl = `${API_URL.replace(/^http/, "ws")}/chat/ws/chat/${selectedSessionId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        setMessages(prev => [
          ...prev,
          {
            id: `ws-${Date.now()}`,
            session_id: selectedSessionId,
            sender: msg.sender || "ai",
            text: msg.text,
            metadata: null,
            created_at: new Date().toISOString(),
          },
        ])
      } catch {
        /* ignore parse errors */
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [selectedSessionId])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = () => {
    if (!replyText.trim() || !selectedSessionId) return

    // Optimistically add the admin message
    setMessages(prev => [
      ...prev,
      {
        id: `local-${Date.now()}`,
        session_id: selectedSessionId,
        sender: "admin",
        text: replyText,
        metadata: null,
        created_at: new Date().toISOString(),
      },
    ])

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ text: replyText }))
    }
    setReplyText("")
  }

  const handleEscalate = async () => {
    if (!selectedSessionId || !token) return
    try {
      await apiFetch("/chat/escalate", token, {
        method: "POST",
        body: JSON.stringify({ session_id: selectedSessionId, reason: "Manual escalation by admin" }),
      })
      toast("Session escalated", "success")
    } catch (e: any) {
      toast(e.message || "Escalation failed", "error")
    }
  }

  const handleAddTag = async () => {
    if (!selectedSessionId || !token || !tagText.trim()) return
    setAddingTag(true)
    try {
      await apiFetch(`/chat/sessions/${selectedSessionId}/tags`, token, {
        method: "POST",
        body: JSON.stringify({ tag: tagText.trim() }),
      })
      toast(`Tag "${tagText.trim()}" added`, "success")
      setTagText("")
      setTagInputOpen(false)
    } catch (e: any) {
      toast(e.message || "Failed to add tag", "error")
    } finally {
      setAddingTag(false)
    }
  }

  const filteredSessions = (sessions ?? []).filter(
    s =>
      s.client_id.toLowerCase().includes(searchConv.toLowerCase()) ||
      s.channel.toLowerCase().includes(searchConv.toLowerCase()),
  )

  if (sessionsLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Bot Conversations</h1>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  if (sessionsError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Bot Conversations</h1>
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-2">
          <AlertCircle className="h-8 w-8" />
          <p className="text-sm">Failed to load conversations: {sessionsError}</p>
        </div>
      </div>
    )
  }

  if (!sessions?.length) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Bot Conversations</h1>
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-2">
          <MessageSquare className="h-8 w-8" />
          <p className="text-sm">No conversations yet</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Bot Conversations</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-0 border border-border rounded-lg overflow-hidden h-[calc(100vh-12rem)]">
        {/* Left Panel - Conversation List */}
        <div className={cn(
          "border-r border-border bg-card overflow-y-auto",
          mobileShowList ? "block" : "hidden lg:block"
        )}>
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search conversations..."
                value={searchConv}
                onChange={(e) => setSearchConv(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
          <div className="divide-y divide-border">
            {filteredSessions.map((session) => (
              <button
                key={session.id}
                onClick={() => {
                  setSelectedSessionId(session.id)
                  setMobileShowList(false)
                }}
                className={cn(
                  "w-full p-3 text-left hover:bg-secondary/50 transition-colors",
                  selectedSessionId === session.id && "bg-secondary"
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{session.client_id}</span>
                  <Badge
                    variant={session.status === "active" ? "success" : "secondary"}
                    className="text-[9px]"
                  >
                    {session.status}
                  </Badge>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <Badge variant="secondary" className="text-[9px] py-0 px-1">
                    {session.channel}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground ml-auto">
                    {formatDateTime(session.created_at)}
                  </span>
                </div>
              </button>
            ))}
            {filteredSessions.length === 0 && (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No matching conversations
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - Conversation Thread */}
        <div className={cn(
          "lg:col-span-2 flex flex-col bg-background",
          mobileShowList ? "hidden lg:flex" : "flex"
        )}>
          {selectedSession ? (
            <>
              {/* Header */}
              <div className="p-3 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    onClick={() => setMobileShowList(true)}
                    className="p-1 rounded-md hover:bg-secondary text-muted-foreground lg:hidden shrink-0"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                  <div className="min-w-0">
                    <h3 className="font-medium truncate">{selectedSession.client_id}</h3>
                    <div className="flex gap-1 mt-0.5">
                      <Badge variant="secondary" className="text-[10px] py-0">
                        {selectedSession.channel}
                      </Badge>
                      <Badge
                        variant={selectedSession.status === "active" ? "success" : "secondary"}
                        className="text-[10px] py-0"
                      >
                        {selectedSession.status}
                      </Badge>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button variant="ghost" size="icon" title="Escalate to human" onClick={handleEscalate}>
                    <Flag className="h-4 w-4" />
                  </Button>
                  <div className="relative">
                    <Button variant="ghost" size="icon" title="Add tag" onClick={() => setTagInputOpen(!tagInputOpen)}>
                      <Tag className="h-4 w-4" />
                    </Button>
                    {tagInputOpen && (
                      <div className="absolute right-0 top-full mt-1 z-50 w-64 rounded-lg border border-border bg-card p-3 shadow-xl">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">Add Tag</span>
                          <button onClick={() => setTagInputOpen(false)} className="text-muted-foreground hover:text-foreground">
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                        <div className="flex gap-2">
                          <Input
                            placeholder="Tag name..."
                            value={tagText}
                            onChange={(e) => setTagText(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") handleAddTag() }}
                            className="text-xs h-8"
                            autoFocus
                          />
                          <Button size="sm" onClick={handleAddTag} disabled={addingTag || !tagText.trim()} className="h-8">
                            {addingTag ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messagesLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                    No messages in this conversation
                  </div>
                ) : (
                  messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={cn(
                        "max-w-[80%] rounded-lg p-3",
                        msg.sender === "user"
                          ? "bg-secondary ml-0"
                          : msg.sender === "admin"
                          ? "bg-emerald-500/10 border border-emerald-500/20 ml-auto"
                          : "bg-blue-500/10 border border-blue-500/20 ml-auto"
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-medium">
                          {msg.sender === "user"
                            ? selectedSession.client_id
                            : msg.sender === "admin"
                            ? "Admin"
                            : "Bot"}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatDateTime(msg.created_at)}
                        </span>
                      </div>
                      <p className="text-sm">{msg.text}</p>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply Input */}
              <div className="p-3 border-t border-border">
                <div className="flex gap-2">
                  <Input
                    placeholder="Type admin reply..."
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSend()
                    }}
                  />
                  <Button onClick={handleSend} disabled={!replyText.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Select a conversation
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
