"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, User, Bot, Headphones, MessageCircle, Loader2, ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiToken, apiFetch, API_URL } from "@/lib/api";
import { useSession } from "next-auth/react";
import { cn } from "@/lib/utils";

interface ChatSession {
  id: string;
  subject: string;
  status: string;
  agent_type?: string;
  last_message?: string;
  last_message_time?: string;
  created_at?: string;
  [key: string]: any;
}

interface ChatMessage {
  id: string;
  sender: string;
  text: string;
  timestamp: string;
  created_at?: string;
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function SupportPage() {
  const { data: session } = useSession();
  const clientId = (session?.user as any)?.clientId;
  const token = useApiToken();

  const { data: chatSessions, loading: sessionsLoading } = useApi<ChatSession[]>(
    clientId ? `/chat/sessions?client_id=${clientId}` : null
  );

  const [activeSessionId, setActiveSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [mobileShowList, setMobileShowList] = useState(false);

  const sessions = chatSessions || [];

  // Set initial active session
  useEffect(() => {
    if (sessions.length > 0 && !activeSessionId) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessions, activeSessionId]);

  // Load messages when session changes
  useEffect(() => {
    if (!activeSessionId || !token) return;
    setMessagesLoading(true);
    apiFetch<ChatMessage[]>(`/chat/sessions/${activeSessionId}/messages`, token)
      .then((msgs) => {
        setMessages(
          msgs.map((m) => ({
            ...m,
            timestamp: m.timestamp || m.created_at || new Date().toISOString(),
          }))
        );
      })
      .catch(() => setMessages([]))
      .finally(() => setMessagesLoading(false));
  }, [activeSessionId, token]);

  // WebSocket connection
  useEffect(() => {
    if (!activeSessionId || !token) return;

    const wsUrl = API_URL.replace(/^http/, "ws");
    const ws = new WebSocket(`${wsUrl}/chat/ws/chat/${activeSessionId}?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const aiMsg: ChatMessage = {
          id: `msg_ws_${Date.now()}`,
          sender: data.sender || "ai",
          text: data.text,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, aiMsg]);
        setSending(false);
      } catch {}
    };

    ws.onerror = () => {
      setSending(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [activeSessionId, token]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  const handleSend = useCallback(() => {
    if (!newMessage.trim() || !activeSession) return;

    const text = newMessage.trim();

    // Add client message to local state
    const clientMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: "client",
      text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, clientMsg]);
    setNewMessage("");
    setSending(true);

    // Send via WebSocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ text }));
    } else {
      // Fallback: just show the message, WS will reconnect
      setSending(false);
    }
  }, [newMessage, activeSession]);

  if (sessionsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Support</h1>
        <p className="text-gray-400">Get help from our AI assistant or human agents</p>
      </div>

      <div className="grid h-[calc(100vh-220px)] gap-4 grid-cols-1 lg:grid-cols-[300px_1fr]">
        {/* Chat List Sidebar — visible on desktop, toggle on mobile */}
        <Card className={cn(
          "flex-col overflow-hidden",
          mobileShowList ? "flex" : "hidden lg:flex"
        )}>
          <CardHeader className="shrink-0 border-b border-gray-800 pb-3">
            <CardTitle className="text-sm">Conversations</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto p-2">
            {sessions.length > 0 ? (
              <div className="space-y-1">
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setActiveSessionId(s.id);
                      setMobileShowList(false);
                    }}
                    className={cn(
                      "w-full rounded-lg p-3 text-left transition-colors",
                      activeSessionId === s.id
                        ? "bg-blue-600/10 border border-blue-800"
                        : "hover:bg-gray-800"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-white truncate">
                        {s.subject || `Chat ${s.id.slice(-6)}`}
                      </p>
                      <Badge
                        variant={s.status === "open" ? "success" : "secondary"}
                        className="ml-2 shrink-0 text-[10px]"
                      >
                        {s.status}
                      </Badge>
                    </div>
                    {s.last_message && (
                      <p className="mt-1 truncate text-xs text-gray-400">
                        {s.last_message}
                      </p>
                    )}
                    <div className="mt-1 flex items-center gap-1 text-[10px] text-gray-500">
                      {s.agent_type === "human" ? (
                        <Headphones className="h-3 w-3" />
                      ) : (
                        <Bot className="h-3 w-3" />
                      )}
                      {s.agent_type === "human" ? "Human Agent" : "AI Assistant"}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="py-4 text-center text-sm text-gray-400">No conversations yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Chat Thread — hidden on mobile when list is shown */}
        <Card className={cn(
          "flex-col overflow-hidden",
          mobileShowList ? "hidden lg:flex" : "flex"
        )}>
          {activeSession ? (
            <>
              {/* Chat Header */}
              <CardHeader className="shrink-0 border-b border-gray-800 pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <button
                      onClick={() => setMobileShowList(true)}
                      className="p-1 rounded-md hover:bg-gray-800 text-gray-400 lg:hidden shrink-0"
                    >
                      <ArrowLeft className="h-4 w-4" />
                    </button>
                    <div className="min-w-0">
                      <CardTitle className="text-sm truncate">
                        {activeSession.subject || `Chat ${activeSession.id.slice(-6)}`}
                      </CardTitle>
                      <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                        {activeSession.agent_type === "human" ? (
                          <>
                            <Headphones className="h-3 w-3 text-green-400" />
                            <span>Human Agent</span>
                          </>
                        ) : (
                          <>
                            <Bot className="h-3 w-3 text-blue-400" />
                            <span>AI Assistant</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  {activeSession.agent_type !== "human" && (
                    <Button variant="outline" size="sm">
                      <Headphones className="mr-2 h-3 w-3" />
                      Request Human
                    </Button>
                  )}
                </div>
              </CardHeader>

              {/* Messages */}
              <CardContent className="flex-1 overflow-y-auto p-4">
                {messagesLoading ? (
                  <div className="flex h-full items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                  </div>
                ) : messages.length > 0 ? (
                  <div className="space-y-4">
                    {messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={cn("flex gap-3", msg.sender === "client" && "flex-row-reverse")}
                      >
                        <div
                          className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                            msg.sender === "client"
                              ? "bg-blue-600"
                              : msg.sender === "ai"
                              ? "bg-gray-700"
                              : "bg-green-700"
                          )}
                        >
                          {msg.sender === "client" ? (
                            <User className="h-4 w-4 text-white" />
                          ) : msg.sender === "ai" ? (
                            <Bot className="h-4 w-4 text-white" />
                          ) : (
                            <Headphones className="h-4 w-4 text-white" />
                          )}
                        </div>
                        <div
                          className={cn(
                            "max-w-[75%] rounded-2xl px-4 py-2",
                            msg.sender === "client"
                              ? "bg-blue-600 text-white"
                              : "bg-gray-800 text-gray-200"
                          )}
                        >
                          <p className="text-sm">{msg.text}</p>
                          <p
                            className={cn(
                              "mt-1 text-[10px]",
                              msg.sender === "client" ? "text-blue-200" : "text-gray-500"
                            )}
                          >
                            {formatTime(msg.timestamp)}
                          </p>
                        </div>
                      </div>
                    ))}
                    {sending && (
                      <div className="flex gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-700">
                          <Bot className="h-4 w-4 text-white" />
                        </div>
                        <div className="rounded-2xl bg-gray-800 px-4 py-2">
                          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <p className="text-sm text-gray-400">No messages yet. Start the conversation!</p>
                  </div>
                )}
              </CardContent>

              {/* Input */}
              <div className="shrink-0 border-t border-gray-800 p-4">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="flex gap-2"
                >
                  <Input
                    placeholder="Type your message..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    className="flex-1"
                  />
                  <Button type="submit" disabled={!newMessage.trim() || sending}>
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <MessageCircle className="mx-auto h-12 w-12 text-gray-700" />
                <p className="mt-2 text-gray-400">
                  {sessions.length === 0 ? "No conversations yet" : "Select a conversation"}
                </p>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
