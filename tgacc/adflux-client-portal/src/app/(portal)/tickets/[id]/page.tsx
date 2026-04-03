"use client";

import React, { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Send,
  User,
  Bot,
  Headphones,
  Loader2,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiToken, apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TicketMessage {
  id: string;
  sender_type: string;
  text: string;
  created_at: string;
}

interface TicketDetail {
  id: string;
  subject: string;
  status: string;
  priority: string;
  category: string;
  created_at: string;
  messages: TicketMessage[];
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

function formatTime(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(date));
}

function SenderAvatar({ sender }: { sender: string }) {
  const colors: Record<string, string> = {
    client: "bg-blue-600",
    admin: "bg-gray-700",
    ai: "bg-purple-700",
  };
  const icons: Record<string, React.ReactNode> = {
    client: <User className="h-4 w-4 text-white" />,
    admin: <Headphones className="h-4 w-4 text-white" />,
    ai: <Bot className="h-4 w-4 text-white" />,
  };

  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
        colors[sender] || colors.admin
      )}
    >
      {icons[sender] || icons.admin}
    </div>
  );
}

export default function TicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const token = useApiToken();
  const ticketId = params.id as string;

  const { data: ticket, loading, refetch } = useApi<TicketDetail>(
    `/tickets/${ticketId}`
  );

  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isClosed = ticket?.status === "closed" || ticket?.status === "resolved";

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [ticket?.messages?.length]);

  const handleReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !replyText.trim() || isClosed) return;
    setSending(true);
    try {
      await apiFetch(`/tickets/${ticketId}/messages`, token, {
        method: "POST",
        body: JSON.stringify({ text: replyText }),
      });
      setReplyText("");
      refetch();
    } catch {
      // error handled silently
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-gray-400">Ticket not found</p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push("/tickets")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Tickets
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => router.push("/tickets")}
          className="mt-1 shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-white truncate">
            {ticket.subject}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge
              className={cn(
                "border-transparent text-white",
                STATUS_COLORS[ticket.status] || STATUS_COLORS.open
              )}
            >
              {STATUS_LABELS[ticket.status] || ticket.status}
            </Badge>
            <Badge variant={PRIORITY_VARIANT[ticket.priority] || "default"}>
              {ticket.priority}
            </Badge>
          </div>
        </div>
      </div>

      {/* Message thread */}
      <Card className="flex flex-col overflow-hidden" style={{ height: "calc(100vh - 260px)" }}>
        <CardContent className="flex-1 overflow-y-auto p-4">
          {ticket.messages && ticket.messages.length > 0 ? (
            <div className="space-y-4">
              {ticket.messages.map((msg) => {
                const isClient = msg.sender_type === "client";
                const isAi = msg.sender_type === "ai";
                return (
                  <div
                    key={msg.id}
                    className={cn("flex gap-3", isClient && "flex-row-reverse")}
                  >
                    <SenderAvatar sender={msg.sender_type} />
                    <div
                      className={cn(
                        "max-w-[75%] rounded-2xl px-4 py-2",
                        isClient
                          ? "bg-blue-600 text-white"
                          : isAi
                          ? "bg-purple-900/50 text-gray-200"
                          : "bg-gray-800 text-gray-200"
                      )}
                    >
                      {isAi && (
                        <p className="mb-1 text-[10px] font-semibold text-purple-400">
                          AI Assistant
                        </p>
                      )}
                      <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                      <p
                        className={cn(
                          "mt-1 text-[10px]",
                          isClient ? "text-blue-200" : "text-gray-500"
                        )}
                      >
                        {formatTime(msg.created_at)}
                      </p>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-gray-400">No messages yet.</p>
            </div>
          )}
        </CardContent>

        {/* Reply form */}
        <div className="shrink-0 border-t border-gray-800 p-4">
          {isClosed ? (
            <p className="text-center text-sm text-gray-500">
              This ticket is {ticket.status}. No further replies can be added.
            </p>
          ) : (
            <form onSubmit={handleReply} className="flex gap-2">
              <textarea
                rows={1}
                placeholder="Type your reply..."
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleReply(e);
                  }
                }}
                className="flex-1 resize-none rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <Button type="submit" disabled={!replyText.trim() || sending}>
                {sending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          )}
        </div>
      </Card>
    </div>
  );
}
