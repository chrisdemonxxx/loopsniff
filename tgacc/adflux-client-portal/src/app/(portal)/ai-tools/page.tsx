"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Sparkles,
  Globe,
  Bot,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Copy,
  Send,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { apiFetch, useApiToken } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Shared helpers                                                     */
/* ------------------------------------------------------------------ */

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    critical: "bg-red-600 text-white",
    high: "bg-orange-600 text-white",
    medium: "bg-yellow-600 text-white",
    low: "bg-blue-600 text-white",
  };
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${map[severity] ?? "bg-gray-600 text-white"}`}>
      {severity}
    </span>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-400" : score >= 50 ? "text-yellow-400" : "text-red-400";
  return <span className={`text-3xl font-bold ${color}`}>{score}</span>;
}

/* ------------------------------------------------------------------ */
/*  1. Compliance Checker                                              */
/* ------------------------------------------------------------------ */

function ComplianceTab() {
  const token = useApiToken();
  const [text, setText] = useState("");
  const [platform, setPlatform] = useState("all");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/ai/compliance/check", token, {
        method: "POST",
        body: JSON.stringify({ text, platform }),
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-blue-400" /> Compliance Checker
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Ad Creative Text</Label>
            <textarea
              rows={5}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your ad copy here..."
              className="mt-1 w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex items-end gap-4">
            <div>
              <Label>Platform</Label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="mt-1 block rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 focus:border-blue-500 focus:outline-none"
              >
                <option value="all">All Platforms</option>
                <option value="meta">Meta (Facebook/Instagram)</option>
                <option value="google">Google Ads</option>
                <option value="tiktok">TikTok</option>
              </select>
            </div>
            <Button onClick={submit} disabled={loading || !text.trim()}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
              Check Compliance
            </Button>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Compliance Score</p>
                <ScoreBadge score={result.score} />
                <span className="ml-2 text-sm text-gray-400">/ 100</span>
              </div>
              <Badge variant={result.score >= 80 ? "success" : result.score >= 50 ? "warning" : "destructive"}>
                {result.summary}
              </Badge>
            </div>

            {result.violations.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-300">Violations</h3>
                <div className="space-y-2">
                  {result.violations.map((v: any, i: number) => (
                    <div key={i} className="flex items-start gap-3 rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                      <SeverityBadge severity={v.severity} />
                      <div className="flex-1">
                        <p className="text-sm text-gray-200">{v.message}</p>
                        {v.matched && <p className="mt-1 text-xs text-gray-500">Matched: &ldquo;{v.matched}&rdquo;</p>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.suggestions.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-300">Suggestions</h3>
                <ul className="list-inside list-disc space-y-1 text-sm text-gray-400">
                  {result.suggestions.map((s: string, i: number) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  2. Creative Generator                                              */
/* ------------------------------------------------------------------ */

function CreativeTab() {
  const token = useApiToken();
  const [mode, setMode] = useState<"generate" | "improve">("generate");

  // Generate state
  const [product, setProduct] = useState("");
  const [audience, setAudience] = useState("general");
  const [tone, setTone] = useState("professional");
  const [genPlatform, setGenPlatform] = useState("meta");
  const [industry, setIndustry] = useState("general");
  const [genResult, setGenResult] = useState<any>(null);

  // Improve state
  const [improveText, setImproveText] = useState("");
  const [impPlatform, setImpPlatform] = useState("meta");
  const [impResult, setImpResult] = useState<any>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    if (!product.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/ai/creative/generate", token, {
        method: "POST",
        body: JSON.stringify({ product, audience, tone, platform: genPlatform, industry }),
      });
      setGenResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const improve = async () => {
    if (!improveText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/ai/creative/improve", token, {
        method: "POST",
        body: JSON.stringify({ text: improveText, platform: impPlatform }),
      });
      setImpResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const copyAll = (items: string[]) => {
    navigator.clipboard.writeText(items.join("\n"));
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-violet-400" /> Creative Generator
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button variant={mode === "generate" ? "default" : "outline"} size="sm" onClick={() => setMode("generate")}>
              Generate New
            </Button>
            <Button variant={mode === "improve" ? "default" : "outline"} size="sm" onClick={() => setMode("improve")}>
              Improve Existing
            </Button>
          </div>

          {mode === "generate" ? (
            <>
              <div>
                <Label>Product / Service Description</Label>
                <textarea
                  rows={3}
                  value={product}
                  onChange={(e) => setProduct(e.target.value)}
                  placeholder="Describe your product or service..."
                  className="mt-1 w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <Label>Audience</Label>
                  <Input value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="e.g. small businesses" />
                </div>
                <div>
                  <Label>Tone</Label>
                  <select value={tone} onChange={(e) => setTone(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100">
                    <option value="professional">Professional</option>
                    <option value="casual">Casual</option>
                    <option value="urgent">Urgent</option>
                    <option value="luxury">Luxury</option>
                  </select>
                </div>
                <div>
                  <Label>Platform</Label>
                  <select value={genPlatform} onChange={(e) => setGenPlatform(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100">
                    <option value="meta">Meta</option>
                    <option value="google">Google</option>
                    <option value="tiktok">TikTok</option>
                  </select>
                </div>
                <div>
                  <Label>Industry</Label>
                  <select value={industry} onChange={(e) => setIndustry(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100">
                    <option value="general">General</option>
                    <option value="ecommerce">E-commerce</option>
                    <option value="saas">SaaS</option>
                    <option value="finance">Finance</option>
                    <option value="health">Health</option>
                    <option value="education">Education</option>
                  </select>
                </div>
              </div>
              <Button onClick={generate} disabled={loading || !product.trim()}>
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                Generate Creatives
              </Button>
            </>
          ) : (
            <>
              <div>
                <Label>Existing Ad Copy</Label>
                <textarea
                  rows={4}
                  value={improveText}
                  onChange={(e) => setImproveText(e.target.value)}
                  placeholder="Paste your existing ad copy..."
                  className="mt-1 w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="flex items-end gap-4">
                <div>
                  <Label>Platform</Label>
                  <select value={impPlatform} onChange={(e) => setImpPlatform(e.target.value)} className="mt-1 block rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100">
                    <option value="meta">Meta</option>
                    <option value="google">Google</option>
                    <option value="tiktok">TikTok</option>
                  </select>
                </div>
                <Button onClick={improve} disabled={loading || !improveText.trim()}>
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  Analyze &amp; Improve
                </Button>
              </div>
            </>
          )}
          {error && <p className="text-sm text-red-400">{error}</p>}
        </CardContent>
      </Card>

      {/* Generate results */}
      {mode === "generate" && genResult && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            {[
              { title: "Headlines", items: genResult.headlines },
              { title: "Primary Text", items: genResult.primary_texts },
              { title: "Descriptions", items: genResult.descriptions },
              { title: "CTA Suggestions", items: genResult.cta_suggestions },
            ].map((section) => (
              <div key={section.title}>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-300">{section.title}</h3>
                  <button onClick={() => copyAll(section.items)} className="text-xs text-blue-400 hover:underline flex items-center gap-1">
                    <Copy className="h-3 w-3" /> Copy All
                  </button>
                </div>
                <div className="space-y-1">
                  {section.items.map((item: string, i: number) => (
                    <div key={i} className="rounded border border-gray-800 bg-gray-900/50 px-3 py-2 text-sm text-gray-200">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Improve results */}
      {mode === "improve" && impResult && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-sm text-gray-400">Overall Score</p>
                <ScoreBadge score={impResult.overall_score} />
                <span className="ml-2 text-sm text-gray-400">/ 100</span>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-300">Analysis</h3>
              <div className="space-y-2">
                {impResult.improvements.map((imp: any, i: number) => (
                  <div key={i} className="flex items-start gap-3 rounded border border-gray-800 bg-gray-900/50 p-3">
                    <Badge variant="outline">{imp.current_score}</Badge>
                    <div>
                      <p className="text-sm font-medium text-gray-200">{imp.category}</p>
                      <p className="text-xs text-gray-400">{imp.suggestion}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-300">Suggested Rewrite</h3>
              <div className="rounded border border-gray-800 bg-gray-900/50 p-3 text-sm text-gray-200">
                {impResult.rewritten}
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-300">Tips</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-gray-400">
                {impResult.tips.map((tip: string, i: number) => (
                  <li key={i}>{tip}</li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  3. Landing Page Analyzer                                           */
/* ------------------------------------------------------------------ */

function LandingPageTab() {
  const token = useApiToken();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/ai/landing-page/analyze", token, {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-emerald-400" /> Landing Page Analyzer
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Landing Page URL</Label>
            <div className="mt-1 flex gap-2">
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/landing"
                className="flex-1"
              />
              <Button onClick={analyze} disabled={loading || !url.trim()}>
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Globe className="mr-2 h-4 w-4" />}
                Analyze
              </Button>
            </div>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Page Score</p>
                <ScoreBadge score={result.score} />
                <span className="ml-2 text-sm text-gray-400">/ 100</span>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">Response Time</p>
                <p className="text-lg font-semibold text-gray-200">{result.load_time_ms}ms</p>
              </div>
            </div>

            <p className="text-sm text-gray-300">{result.summary}</p>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-300">Checks</h3>
              <div className="space-y-2">
                {result.issues.map((issue: any, i: number) => (
                  <div key={i} className="flex items-start gap-3 rounded border border-gray-800 bg-gray-900/50 p-3">
                    {issue.passed ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-400" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                    )}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200">{issue.check}</span>
                        {!issue.passed && <SeverityBadge severity={issue.severity} />}
                      </div>
                      <p className="text-xs text-gray-400">{issue.message}</p>
                      {issue.details && <p className="mt-1 text-xs text-gray-500">{issue.details}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {result.recommendations.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-300">Recommendations</h3>
                <ul className="list-inside list-disc space-y-1 text-sm text-gray-400">
                  {result.recommendations.map((r: string, i: number) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  4. AI Assistant (RAG)                                              */
/* ------------------------------------------------------------------ */

interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: any[];
  confidence?: number;
}

function RAGTab() {
  const token = useApiToken();
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    if (!query.trim()) return;
    const userMsg: Message = { role: "user", text: query };
    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/ai/rag/query", token, {
        method: "POST",
        body: JSON.stringify({ query: userMsg.text, n_results: 5 }),
      });
      const assistantMsg: Message = {
        role: "assistant",
        text: res.answer,
        sources: res.sources,
        confidence: res.confidence,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-amber-400" /> AI Assistant
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-400">
            Ask questions about ad optimization, platform policies, and best practices. Powered by our knowledge base.
          </p>

          {/* Chat history */}
          <div className="max-h-96 space-y-3 overflow-y-auto rounded-lg border border-gray-800 bg-gray-950 p-4">
            {messages.length === 0 && (
              <p className="text-center text-sm text-gray-600">No messages yet. Ask a question below.</p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-200"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                  {msg.confidence !== undefined && (
                    <p className="mt-1 text-xs opacity-70">Confidence: {(msg.confidence * 100).toFixed(0)}%</p>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs opacity-70 hover:opacity-100">
                        {msg.sources.length} source(s)
                      </summary>
                      <div className="mt-1 space-y-1">
                        {msg.sources.map((s: any, j: number) => (
                          <p key={j} className="truncate text-xs opacity-60">
                            {s.metadata?.category || s.metadata?.source || "Knowledge Base"}: {s.text?.slice(0, 80)}…
                          </p>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="rounded-lg bg-gray-800 px-4 py-2">
                  <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about ad optimization, policies, best practices..."
              className="flex-1"
              onKeyDown={(e) => e.key === "Enter" && !loading && ask()}
            />
            <Button onClick={ask} disabled={loading || !query.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </CardContent>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function AIToolsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Tools</h1>
        <p className="text-gray-400">AI-powered tools to optimize your advertising campaigns.</p>
      </div>

      <Tabs defaultValue="compliance">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="compliance" className="gap-1.5">
            <ShieldCheck className="hidden h-4 w-4 sm:inline" /> Compliance
          </TabsTrigger>
          <TabsTrigger value="creative" className="gap-1.5">
            <Sparkles className="hidden h-4 w-4 sm:inline" /> Creative
          </TabsTrigger>
          <TabsTrigger value="landing" className="gap-1.5">
            <Globe className="hidden h-4 w-4 sm:inline" /> Landing Page
          </TabsTrigger>
          <TabsTrigger value="assistant" className="gap-1.5">
            <Bot className="hidden h-4 w-4 sm:inline" /> AI Assistant
          </TabsTrigger>
        </TabsList>

        <TabsContent value="compliance">
          <ComplianceTab />
        </TabsContent>
        <TabsContent value="creative">
          <CreativeTab />
        </TabsContent>
        <TabsContent value="landing">
          <LandingPageTab />
        </TabsContent>
        <TabsContent value="assistant">
          <RAGTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
