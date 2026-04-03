"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import {
  Plus,
  Search,
  ChevronDown,
  Pause,
  Play,
  Trash2,
  MoreHorizontal,
  TrendingUp,
  MousePointerClick,
  Eye,
  DollarSign,
  Megaphone,
  ImageIcon,
  LayoutList,
} from "lucide-react"
import { useApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"

/* ---------- types ---------- */
interface Campaign {
  id: string
  name: string
  status: "ACTIVE" | "PAUSED" | "DELETED" | "ARCHIVED"
  objective: string
  daily_budget?: number
  lifetime_budget?: number
  spend: number
  impressions: number
  clicks: number
  conversions: number
}

interface AdSet {
  id: string
  name: string
  campaign_id: string
  status: "ACTIVE" | "PAUSED" | "DELETED"
  daily_budget?: number
  spend: number
  impressions: number
  clicks: number
  conversions: number
}

interface Ad {
  id: string
  name: string
  adset_id: string
  status: "ACTIVE" | "PAUSED" | "DELETED"
  spend: number
  impressions: number
  clicks: number
  conversions: number
  creative_thumbnail?: string
}

/* ---------- helpers ---------- */
const fmt = (n: number) =>
  new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n)
const fmtCurrency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)
const ctr = (clicks: number, impressions: number) =>
  impressions > 0 ? ((clicks / impressions) * 100).toFixed(2) + "%" : "0%"
const cpc = (spend: number, clicks: number) =>
  clicks > 0 ? fmtCurrency(spend / clicks) : "—"

const statusBadge = (status: string) => {
  switch (status) {
    case "ACTIVE":
      return <Badge variant="success">Active</Badge>
    case "PAUSED":
      return <Badge variant="secondary">Paused</Badge>
    case "DELETED":
      return <Badge variant="destructive">Deleted</Badge>
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

const DATE_RANGES = [
  { label: "Today", value: "today" },
  { label: "Yesterday", value: "yesterday" },
  { label: "Last 7 days", value: "7d" },
  { label: "Last 30 days", value: "30d" },
  { label: "This month", value: "this_month" },
  { label: "Last month", value: "last_month" },
]

/* ---------- empty state ---------- */
function EmptyState({ type }: { type: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-800">
        {type === "campaigns" && <Megaphone className="h-8 w-8 text-gray-500" />}
        {type === "adsets" && <LayoutList className="h-8 w-8 text-gray-500" />}
        {type === "ads" && <ImageIcon className="h-8 w-8 text-gray-500" />}
      </div>
      <h3 className="mb-1 text-lg font-semibold text-white">No {type} yet</h3>
      <p className="mb-6 max-w-sm text-sm text-gray-400">
        {type === "campaigns"
          ? "Create your first campaign to start advertising on Meta platforms."
          : `No ${type} found. Create a campaign to get started.`}
      </p>
      {type === "campaigns" && (
        <Link href="/ads-manager/create">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Campaign
          </Button>
        </Link>
      )}
    </div>
  )
}

/* ---------- main page ---------- */
export default function AdsManagerPage() {
  const [search, setSearch] = useState("")
  const [dateRange, setDateRange] = useState("7d")
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [tab, setTab] = useState("campaigns")

  const { data: campaigns, loading: loadingC } = useApi<Campaign[]>("/meta/campaigns")
  const { data: adSets, loading: loadingAS } = useApi<AdSet[]>("/meta/adsets")
  const { data: ads, loading: loadingA } = useApi<Ad[]>("/meta/ads")

  const filteredCampaigns = useMemo(
    () =>
      (campaigns ?? []).filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase())
      ),
    [campaigns, search]
  )
  const filteredAdSets = useMemo(
    () =>
      (adSets ?? []).filter((a) =>
        a.name.toLowerCase().includes(search.toLowerCase())
      ),
    [adSets, search]
  )
  const filteredAds = useMemo(
    () =>
      (ads ?? []).filter((a) =>
        a.name.toLowerCase().includes(search.toLowerCase())
      ),
    [ads, search]
  )

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = (ids: string[]) => {
    setSelectedIds((prev) => {
      const allSelected = ids.every((id) => prev.has(id))
      if (allSelected) return new Set()
      return new Set(ids)
    })
  }

  const hasSelection = selectedIds.size > 0

  /* ---------- summary metrics ---------- */
  const totalSpend = (campaigns ?? []).reduce((s, c) => s + c.spend, 0)
  const totalImpressions = (campaigns ?? []).reduce((s, c) => s + c.impressions, 0)
  const totalClicks = (campaigns ?? []).reduce((s, c) => s + c.clicks, 0)
  const totalConversions = (campaigns ?? []).reduce((s, c) => s + c.conversions, 0)

  const metrics = [
    { label: "Total Spend", value: fmtCurrency(totalSpend), icon: DollarSign, color: "text-green-400" },
    { label: "Impressions", value: fmt(totalImpressions), icon: Eye, color: "text-blue-400" },
    { label: "Clicks", value: fmt(totalClicks), icon: MousePointerClick, color: "text-purple-400" },
    { label: "Conversions", value: fmt(totalConversions), icon: TrendingUp, color: "text-amber-400" },
  ]

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Ads Manager</h1>
          <p className="text-sm text-gray-400">Manage your Meta advertising campaigns</p>
        </div>
        <Link href="/ads-manager/create">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Campaign
          </Button>
        </Link>
      </div>

      {/* metric cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-lg border border-gray-800 bg-gray-900 p-4">
            <div className="flex items-center gap-2">
              <m.icon className={`h-4 w-4 ${m.color}`} />
              <span className="text-xs text-gray-400">{m.label}</span>
            </div>
            <p className="mt-1 text-xl font-semibold text-white">{m.value}</p>
          </div>
        ))}
      </div>

      {/* filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <Input
            placeholder="Search campaigns…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={dateRange} onValueChange={setDateRange}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DATE_RANGES.map((r) => (
              <SelectItem key={r.value} value={r.value}>
                {r.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasSelection && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{selectedIds.size} selected</span>
            <Button size="sm" variant="secondary">
              <Play className="mr-1 h-3 w-3" /> Enable
            </Button>
            <Button size="sm" variant="secondary">
              <Pause className="mr-1 h-3 w-3" /> Pause
            </Button>
            <Button size="sm" variant="destructive">
              <Trash2 className="mr-1 h-3 w-3" /> Delete
            </Button>
          </div>
        )}
      </div>

      {/* tabs */}
      <Tabs value={tab} onValueChange={(v) => { setTab(v); setSelectedIds(new Set()) }}>
        <TabsList>
          <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          <TabsTrigger value="adsets">Ad Sets</TabsTrigger>
          <TabsTrigger value="ads">Ads</TabsTrigger>
        </TabsList>

        {/* ---- Campaigns ---- */}
        <TabsContent value="campaigns">
          {loadingC ? (
            <LoadingSkeleton />
          ) : filteredCampaigns.length === 0 ? (
            <EmptyState type="campaigns" />
          ) : (
            <div className="rounded-lg border border-gray-800">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input
                        type="checkbox"
                        className="rounded border-gray-600 bg-gray-800"
                        checked={filteredCampaigns.length > 0 && filteredCampaigns.every((c) => selectedIds.has(c.id))}
                        onChange={() => toggleAll(filteredCampaigns.map((c) => c.id))}
                      />
                    </TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="w-20">Status</TableHead>
                    <TableHead className="text-right">Budget</TableHead>
                    <TableHead className="text-right">Spend</TableHead>
                    <TableHead className="text-right">Impressions</TableHead>
                    <TableHead className="text-right">Clicks</TableHead>
                    <TableHead className="text-right">CTR</TableHead>
                    <TableHead className="text-right">CPC</TableHead>
                    <TableHead className="text-right">Conversions</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredCampaigns.map((c) => (
                    <TableRow key={c.id} className={selectedIds.has(c.id) ? "bg-blue-600/5" : ""}>
                      <TableCell>
                        <input
                          type="checkbox"
                          className="rounded border-gray-600 bg-gray-800"
                          checked={selectedIds.has(c.id)}
                          onChange={() => toggleSelect(c.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium text-white">{c.name}</p>
                          <p className="text-xs text-gray-500">{c.objective}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={c.status === "ACTIVE"}
                            onCheckedChange={() => {}}
                            className="scale-75"
                          />
                          {statusBadge(c.status)}
                        </div>
                      </TableCell>
                      <TableCell className="text-right text-gray-300">
                        {c.daily_budget
                          ? `${fmtCurrency(c.daily_budget)}/day`
                          : c.lifetime_budget
                          ? fmtCurrency(c.lifetime_budget)
                          : "—"}
                      </TableCell>
                      <TableCell className="text-right text-gray-300">{fmtCurrency(c.spend)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(c.impressions)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(c.clicks)}</TableCell>
                      <TableCell className="text-right text-gray-300">{ctr(c.clicks, c.impressions)}</TableCell>
                      <TableCell className="text-right text-gray-300">{cpc(c.spend, c.clicks)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(c.conversions)}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* ---- Ad Sets ---- */}
        <TabsContent value="adsets">
          {loadingAS ? (
            <LoadingSkeleton />
          ) : filteredAdSets.length === 0 ? (
            <EmptyState type="adsets" />
          ) : (
            <div className="rounded-lg border border-gray-800">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input
                        type="checkbox"
                        className="rounded border-gray-600 bg-gray-800"
                        checked={filteredAdSets.length > 0 && filteredAdSets.every((a) => selectedIds.has(a.id))}
                        onChange={() => toggleAll(filteredAdSets.map((a) => a.id))}
                      />
                    </TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="w-20">Status</TableHead>
                    <TableHead className="text-right">Budget</TableHead>
                    <TableHead className="text-right">Spend</TableHead>
                    <TableHead className="text-right">Impressions</TableHead>
                    <TableHead className="text-right">Clicks</TableHead>
                    <TableHead className="text-right">CTR</TableHead>
                    <TableHead className="text-right">CPC</TableHead>
                    <TableHead className="text-right">Conversions</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAdSets.map((a) => (
                    <TableRow key={a.id} className={selectedIds.has(a.id) ? "bg-blue-600/5" : ""}>
                      <TableCell>
                        <input
                          type="checkbox"
                          className="rounded border-gray-600 bg-gray-800"
                          checked={selectedIds.has(a.id)}
                          onChange={() => toggleSelect(a.id)}
                        />
                      </TableCell>
                      <TableCell className="font-medium text-white">{a.name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch checked={a.status === "ACTIVE"} onCheckedChange={() => {}} className="scale-75" />
                          {statusBadge(a.status)}
                        </div>
                      </TableCell>
                      <TableCell className="text-right text-gray-300">
                        {a.daily_budget ? `${fmtCurrency(a.daily_budget)}/day` : "—"}
                      </TableCell>
                      <TableCell className="text-right text-gray-300">{fmtCurrency(a.spend)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(a.impressions)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(a.clicks)}</TableCell>
                      <TableCell className="text-right text-gray-300">{ctr(a.clicks, a.impressions)}</TableCell>
                      <TableCell className="text-right text-gray-300">{cpc(a.spend, a.clicks)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(a.conversions)}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* ---- Ads ---- */}
        <TabsContent value="ads">
          {loadingA ? (
            <LoadingSkeleton />
          ) : filteredAds.length === 0 ? (
            <EmptyState type="ads" />
          ) : (
            <div className="rounded-lg border border-gray-800">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input
                        type="checkbox"
                        className="rounded border-gray-600 bg-gray-800"
                        checked={filteredAds.length > 0 && filteredAds.every((a) => selectedIds.has(a.id))}
                        onChange={() => toggleAll(filteredAds.map((a) => a.id))}
                      />
                    </TableHead>
                    <TableHead>Ad</TableHead>
                    <TableHead className="w-20">Status</TableHead>
                    <TableHead className="text-right">Spend</TableHead>
                    <TableHead className="text-right">Impressions</TableHead>
                    <TableHead className="text-right">Clicks</TableHead>
                    <TableHead className="text-right">CTR</TableHead>
                    <TableHead className="text-right">CPC</TableHead>
                    <TableHead className="text-right">Conversions</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAds.map((a) => (
                    <TableRow key={a.id} className={selectedIds.has(a.id) ? "bg-blue-600/5" : ""}>
                      <TableCell>
                        <input
                          type="checkbox"
                          className="rounded border-gray-600 bg-gray-800"
                          checked={selectedIds.has(a.id)}
                          onChange={() => toggleSelect(a.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          {a.creative_thumbnail ? (
                            <img src={a.creative_thumbnail} alt="" className="h-10 w-10 rounded object-cover" />
                          ) : (
                            <div className="flex h-10 w-10 items-center justify-center rounded bg-gray-800">
                              <ImageIcon className="h-5 w-5 text-gray-500" />
                            </div>
                          )}
                          <span className="font-medium text-white">{a.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch checked={a.status === "ACTIVE"} onCheckedChange={() => {}} className="scale-75" />
                          {statusBadge(a.status)}
                        </div>
                      </TableCell>
                      <TableCell className="text-right text-gray-300">{fmtCurrency(a.spend)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(a.impressions)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(a.clicks)}</TableCell>
                      <TableCell className="text-right text-gray-300">{ctr(a.clicks, a.impressions)}</TableCell>
                      <TableCell className="text-right text-gray-300">{cpc(a.spend, a.clicks)}</TableCell>
                      <TableCell className="text-right text-gray-300">{fmt(a.conversions)}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3 py-8">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <div className="h-4 w-4 rounded bg-gray-800" />
          <div className="h-4 flex-1 rounded bg-gray-800" />
          <div className="h-4 w-20 rounded bg-gray-800" />
          <div className="h-4 w-16 rounded bg-gray-800" />
          <div className="h-4 w-16 rounded bg-gray-800" />
        </div>
      ))}
    </div>
  )
}
