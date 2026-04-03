"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { useSession } from "next-auth/react"
import { apiFetch, useApiToken } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  MessageCircle,
  X,
  Send,
  Minimize2,
  Plus,
  Loader2,
  ChevronLeft,
} from "lucide-react"

type Message = {
  id: string
  session_id: string
  sender: string
  text: string
  created_at: string
}

type Conversation = {
  id: string
  client_id: string | null
  status: string
  subject: string
  last_message: string | null
  last_message_time: string | null
  created_at: string
  messages?: Message[]
}

export function ChatWidget() {
  const { data: session } = useSession()
  const token = useApiToken()
  const [open, setOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(false)
  const [unread, setUnread] = useState(0)
  const [view, setView] = useState<"list" | "chat">("list")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  // Fetch unread count periodically
  useEffect(() => {
    if (!token) return
    const fetchUnread = async () => {
      try {
        const data = await apiFetch<{ unread: number }>("/chat/unread-count", token)
        setUnread(data.unread)
      } catch {
        // ignore
      }
    }
    fetchUnread()
    const interval = setInterval(fetchUnread, 30_000)
    return () => clearInterval(interval)
  }, [token])

  // Fetch conversations when panel opens
  useEffect(() => {
    if (!open || !token) return
    const fetchConversations = async () => {
      setLoading(true)
      try {
        const data = await apiFetch<Conversation[]>("/chat/conversations", token)
        setConversations(data)
        // Auto-open the first active conversation
        const active = data.find((c) => c.status !== "closed")
        if (active && !activeConversation) {
          loadConversation(active.id)
        }
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    fetchConversations()
  }, [open, token]) // eslint-disable-line react-hooks/exhaustive-deps

  // Poll messages when viewing a conversation
  useEffect(() => {
    if (!activeConversation || !token) return
    const poll = async () => {
      try {
        const data = await apiFetch<Conversation>(
          `/chat/conversations/${activeConversation.id}`,
          token
        )
        if (data.messages) setMessages(data.messages)
      } catch {
        // ignore
      }
    }
    pollRef.current = setInterval(poll, 5_000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [activeConversation, token])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const loadConversation = async (id: string) => {
    if (!token) return
    setLoading(true)
    try {
      const data = await apiFetch<Conversation>(`/chat/conversations/${id}`, token)
      setActiveConversation(data)
      setMessages(data.messages || [])
      setView("chat")
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const startNewConversation = async () => {
    if (!token) return
    setLoading(true)
    try {
      const data = await apiFetch<Conversation>("/chat/conversations", token, {
        method: "POST",
        body: JSON.stringify({ subject: "Support Chat" }),
      })
      setActiveConversation(data)
      setMessages([])
      setView("chat")
      setConversations((prev) => [data, ...prev])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !activeConversation || !token || sending) return
    const text = input.trim()
    setInput("")
    setSending(true)

    // Optimistic update
    const optimistic: Message = {
      id: `temp-${Date.now()}`,
      session_id: activeConversation.id,
      sender: "user",
      text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimistic])

    try {
      const msg = await apiFetch<Message>(
        `/chat/conversations/${activeConversation.id}/messages`,
        token,
        { method: "POST", body: JSON.stringify({ text }) }
      )
      setMessages((prev) => prev.map((m) => (m.id === optimistic.id ? msg : m)))
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id))
      setInput(text)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  function timeAgo(dateStr: string | null): string {
    if (!dateStr) return ""
    const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
    if (seconds < 60) return "just now"
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  if (!session) return null

  return (
    <>
      {/* Floating bubble */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-white shadow-lg transition-transform hover:scale-105 active:scale-95"
        >
          <MessageCircle className="h-6 w-6" />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 flex h-[500px] w-[350px] flex-col overflow-hidden rounded-2xl border border-gray-800 bg-gray-950 shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900 px-4 py-3">
            <div className="flex items-center gap-2">
              {view === "chat" && activeConversation && (
                <button
                  onClick={() => {
                    setView("list")
                    setActiveConversation(null)
                  }}
                  className="mr-1 rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
              )}
              <MessageCircle className="h-5 w-5 text-emerald-400" />
              <span className="font-semibold text-white">
                {view === "chat" ? "Support Chat" : "Messages"}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setOpen(false)}
                className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
              >
                <Minimize2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => {
                  setOpen(false)
                  setActiveConversation(null)
                  setView("list")
                }}
                className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Body */}
          {view === "list" ? (
            <div className="flex flex-1 flex-col overflow-y-auto">
              {loading ? (
                <div className="flex flex-1 items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              ) : (
                <>
                  {/* New conversation button */}
                  <button
                    onClick={startNewConversation}
                    className="mx-3 mt-3 flex items-center gap-2 rounded-lg border border-dashed border-gray-700 px-4 py-3 text-sm text-gray-400 transition-colors hover:border-emerald-500 hover:text-emerald-400"
                  >
                    <Plus className="h-4 w-4" />
                    Start new conversation
                  </button>

                  {/* Conversation list */}
                  {conversations.length === 0 ? (
                    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
                      <MessageCircle className="h-10 w-10 text-gray-700" />
                      <p className="text-sm text-gray-400">No conversations yet</p>
                      <p className="text-xs text-gray-600">
                        Start a new conversation to get help
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1 p-3">
                      {conversations.map((conv) => (
                        <button
                          key={conv.id}
                          onClick={() => loadConversation(conv.id)}
                          className="flex flex-col gap-1 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-gray-900"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-white">
                              {conv.subject || "Support Chat"}
                            </span>
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 text-xs",
                                conv.status === "closed"
                                  ? "bg-gray-800 text-gray-500"
                                  : "bg-emerald-500/10 text-emerald-400"
                              )}
                            >
                              {conv.status}
                            </span>
                          </div>
                          {conv.last_message && (
                            <p className="truncate text-xs text-gray-500">
                              {conv.last_message}
                            </p>
                          )}
                          {conv.last_message_time && (
                            <p className="text-xs text-gray-600">
                              {timeAgo(conv.last_message_time)}
                            </p>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <>
              {/* Messages */}
              <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-4">
                {loading ? (
                  <div className="flex flex-1 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
                    <MessageCircle className="h-8 w-8 text-gray-700" />
                    <p className="text-sm text-gray-400">
                      Send a message to start the conversation
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={cn(
                        "flex",
                        msg.sender === "user" ? "justify-end" : "justify-start"
                      )}
                    >
                      <div
                        className={cn(
                          "max-w-[80%] rounded-2xl px-3.5 py-2 text-sm",
                          msg.sender === "user"
                            ? "rounded-br-md bg-emerald-500 text-white"
                            : "rounded-bl-md bg-gray-800 text-gray-200"
                        )}
                      >
                        {msg.sender !== "user" && (
                          <p className="mb-0.5 text-xs font-medium text-emerald-400">
                            {msg.sender === "ai" ? "AI Assistant" : "Support"}
                          </p>
                        )}
                        <p className="whitespace-pre-wrap">{msg.text}</p>
                        <p
                          className={cn(
                            "mt-1 text-right text-[10px]",
                            msg.sender === "user"
                              ? "text-emerald-200"
                              : "text-gray-500"
                          )}
                        >
                          {timeAgo(msg.created_at)}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="border-t border-gray-800 bg-gray-900 p-3">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a message…"
                    className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 outline-none focus:border-emerald-500"
                    disabled={sending}
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!input.trim() || sending}
                    className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 text-white transition-colors hover:bg-emerald-600 disabled:opacity-40"
                  >
                    {sending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  )
}
