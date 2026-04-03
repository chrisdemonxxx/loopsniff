"use client"

import { useRouter } from "next/navigation"
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Globe,
  MousePointerClick,
  ShoppingCart,
  Users,
  Heart,
  Smartphone,
  Upload,
  X,
  ChevronRight,
  MessageCircle,
  Monitor,
  Sparkles,
  Image as ImageIcon,
  Film,
  LayoutGrid,
  Save,
  Rocket,
  ThumbsUp,
  Camera,
} from "lucide-react"
import { useWizard } from "./wizard-context"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { useCallback, useRef, useState } from "react"

/* ==========================================================================
   CONSTANTS
   ========================================================================== */

const OBJECTIVES = [
  { id: "traffic", label: "Traffic", desc: "Send people to a destination like a website or app.", icon: Globe },
  { id: "leads", label: "Leads", desc: "Collect leads for your business via forms, calls or messages.", icon: MousePointerClick },
  { id: "sales", label: "Sales", desc: "Find people likely to purchase your product or service.", icon: ShoppingCart },
  { id: "awareness", label: "Awareness", desc: "Reach people who are most likely to remember your ad.", icon: Users },
  { id: "engagement", label: "Engagement", desc: "Get more messages, video views, post engagement or page likes.", icon: Heart },
  { id: "app_promotion", label: "App Promotion", desc: "Find people to install and engage with your mobile app.", icon: Smartphone },
]

const SPECIAL_CATEGORIES = [
  { id: "credit", label: "Credit" },
  { id: "employment", label: "Employment" },
  { id: "housing", label: "Housing" },
  { id: "social_issues", label: "Social Issues, Elections or Politics" },
]

const BID_STRATEGIES = [
  { value: "lowest_cost", label: "Lowest Cost" },
  { value: "bid_cap", label: "Bid Cap" },
  { value: "cost_cap", label: "Cost Cap" },
]

const REGION_PRESETS = [
  { id: "eea", label: "EEA", countries: ["Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"] },
  { id: "europe", label: "Europe", countries: ["United Kingdom", "Switzerland", "Norway"] },
  { id: "usmca", label: "USMCA", countries: ["United States", "Mexico", "Canada"] },
]

const LANGUAGES = [
  "English", "Spanish", "French", "German", "Portuguese", "Italian",
  "Dutch", "Arabic", "Chinese", "Japanese", "Korean", "Hindi",
  "Russian", "Turkish", "Polish", "Swedish", "Norwegian", "Danish",
]

const OPTIMIZATION_GOALS = [
  { value: "link_clicks", label: "Link Clicks" },
  { value: "landing_page_views", label: "Landing Page Views" },
  { value: "impressions", label: "Impressions" },
  { value: "reach", label: "Reach" },
]

const BILLING_EVENTS = [
  { value: "impressions", label: "Impressions" },
  { value: "link_clicks", label: "Link Clicks" },
]

const PLACEMENT_GROUPS = [
  {
    platform: "Facebook",
    icon: ThumbsUp,
    placements: ["Feed", "Stories", "Reels", "Marketplace", "Video Feeds", "Right Column", "In-Stream", "Search"],
  },
  {
    platform: "Instagram",
    icon: Camera,
    placements: ["Feed", "Stories", "Reels", "Explore", "Profile"],
  },
  {
    platform: "Messenger",
    icon: MessageCircle,
    placements: ["Inbox", "Stories", "Sponsored Messages"],
  },
  {
    platform: "Audience Network",
    icon: Monitor,
    placements: ["Native", "Banner", "Interstitial", "Rewarded Video"],
  },
]

const CTA_OPTIONS = [
  { value: "learn_more", label: "Learn More" },
  { value: "shop_now", label: "Shop Now" },
  { value: "sign_up", label: "Sign Up" },
  { value: "contact_us", label: "Contact Us" },
  { value: "download", label: "Download" },
  { value: "get_offer", label: "Get Offer" },
  { value: "book_now", label: "Book Now" },
  { value: "apply_now", label: "Apply Now" },
  { value: "subscribe", label: "Subscribe" },
  { value: "watch_more", label: "Watch More" },
  { value: "send_message", label: "Send Message" },
]

const STEPS = ["Objective", "Campaign", "Ad Set", "Ad Creative", "Review"]

/* ==========================================================================
   PAGE
   ========================================================================== */

export default function CreateCampaignPage() {
  const { step, nextStep, prevStep, goToStep, canProceed, data, updateData } = useWizard()
  const router = useRouter()

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/ads-manager")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-white">Create Campaign</h1>
          <p className="text-sm text-gray-400">Step {step + 1} of 5 — {STEPS[step]}</p>
        </div>
      </div>

      {/* stepper */}
      <Stepper currentStep={step} onStepClick={goToStep} />

      {/* step content */}
      <div className="min-h-[400px]">
        {step === 0 && <StepObjective />}
        {step === 1 && <StepCampaignSettings />}
        {step === 2 && <StepAdSet />}
        {step === 3 && <StepAdCreative />}
        {step === 4 && <StepReview />}
      </div>

      {/* nav */}
      <div className="flex items-center justify-between border-t border-gray-800 pt-6">
        <Button variant="outline" onClick={prevStep} disabled={step === 0}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <div className="flex gap-3">
          {step === 4 ? (
            <>
              <Button variant="secondary" onClick={() => router.push("/ads-manager")}>
                <Save className="mr-2 h-4 w-4" /> Save as Draft
              </Button>
              <Button onClick={() => router.push("/ads-manager")}>
                <Rocket className="mr-2 h-4 w-4" /> Publish Campaign
              </Button>
            </>
          ) : (
            <Button onClick={nextStep} disabled={!canProceed}>
              Next <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ==========================================================================
   STEPPER
   ========================================================================== */

function Stepper({ currentStep, onStepClick }: { currentStep: number; onStepClick: (s: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      {STEPS.map((label, i) => {
        const isCompleted = i < currentStep
        const isCurrent = i === currentStep
        return (
          <div key={label} className="flex items-center gap-2">
            <button
              onClick={() => onStepClick(i)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isCurrent && "bg-blue-600/10 text-blue-400",
                isCompleted && "text-green-400 hover:bg-gray-800",
                !isCurrent && !isCompleted && "text-gray-500 hover:bg-gray-800"
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                  isCurrent && "bg-blue-600 text-white",
                  isCompleted && "bg-green-600 text-white",
                  !isCurrent && !isCompleted && "bg-gray-800 text-gray-400"
                )}
              >
                {isCompleted ? <Check className="h-3 w-3" /> : i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </button>
            {i < STEPS.length - 1 && <ChevronRight className="h-4 w-4 text-gray-600" />}
          </div>
        )
      })}
    </div>
  )
}

/* ==========================================================================
   STEP 1 — OBJECTIVE
   ========================================================================== */

function StepObjective() {
  const { data, updateData } = useWizard()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Choose a campaign objective</h2>
        <p className="text-sm text-gray-400">Your objective determines how Meta optimizes the delivery of your ads.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {OBJECTIVES.map((obj) => {
          const selected = data.objective === obj.id
          return (
            <button
              key={obj.id}
              onClick={() => updateData({ objective: obj.id })}
              className={cn(
                "flex flex-col items-start gap-3 rounded-lg border p-5 text-left transition-all hover:border-blue-500/50",
                selected
                  ? "border-blue-500 bg-blue-600/10 ring-2 ring-blue-500"
                  : "border-gray-700 bg-gray-800/50"
              )}
            >
              <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", selected ? "bg-blue-600" : "bg-gray-700")}>
                <obj.icon className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-white">{obj.label}</p>
                <p className="mt-1 text-xs text-gray-400">{obj.desc}</p>
              </div>
              {selected && (
                <div className="ml-auto">
                  <Check className="h-5 w-5 text-blue-400" />
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/* ==========================================================================
   STEP 2 — CAMPAIGN SETTINGS
   ========================================================================== */

function StepCampaignSettings() {
  const { data, updateData } = useWizard()

  const toggleCategory = (id: string) => {
    const current = data.specialCategories
    updateData({
      specialCategories: current.includes(id)
        ? current.filter((c) => c !== id)
        : [...current, id],
    })
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-white">Campaign Settings</h2>
        <p className="text-sm text-gray-400">Configure your campaign name, budget, and schedule.</p>
      </div>

      {/* Campaign Name */}
      <div className="space-y-2">
        <Label>Campaign Name *</Label>
        <Input
          placeholder="e.g. Summer Sale 2025"
          value={data.campaignName}
          onChange={(e) => updateData({ campaignName: e.target.value })}
        />
      </div>

      {/* Special Ad Categories */}
      <div className="space-y-3">
        <Label>Special Ad Categories</Label>
        <p className="text-xs text-gray-500">Declare if your ads relate to credit, employment, housing, or social issues.</p>
        <div className="flex flex-wrap gap-2">
          {SPECIAL_CATEGORIES.map((cat) => {
            const selected = data.specialCategories.includes(cat.id)
            return (
              <button
                key={cat.id}
                onClick={() => toggleCategory(cat.id)}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  selected
                    ? "border-blue-500 bg-blue-600/10 text-blue-400"
                    : "border-gray-700 text-gray-400 hover:border-gray-600"
                )}
              >
                {selected && <Check className="mr-1 inline h-3 w-3" />}
                {cat.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Budget Optimization */}
      <div className="space-y-4 rounded-lg border border-gray-700 bg-gray-800/50 p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-white">Campaign Budget Optimization</p>
            <p className="text-xs text-gray-400">Automatically distribute budget across ad sets for best results.</p>
          </div>
          <Switch
            checked={data.budgetOptimization === "campaign"}
            onCheckedChange={(checked) =>
              updateData({ budgetOptimization: checked ? "campaign" : "adset" })
            }
          />
        </div>

        {data.budgetOptimization === "campaign" && (
          <div className="space-y-4 border-t border-gray-700 pt-4">
            <div className="flex gap-3">
              <button
                onClick={() => updateData({ budgetType: "daily" })}
                className={cn(
                  "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                  data.budgetType === "daily"
                    ? "border-blue-500 bg-blue-600/10 text-blue-400"
                    : "border-gray-700 text-gray-400 hover:border-gray-600"
                )}
              >
                Daily Budget
              </button>
              <button
                onClick={() => updateData({ budgetType: "lifetime" })}
                className={cn(
                  "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                  data.budgetType === "lifetime"
                    ? "border-blue-500 bg-blue-600/10 text-blue-400"
                    : "border-gray-700 text-gray-400 hover:border-gray-600"
                )}
              >
                Lifetime Budget
              </button>
            </div>
            <div className="space-y-2">
              <Label>{data.budgetType === "daily" ? "Daily Budget (USD)" : "Lifetime Budget (USD)"}</Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">$</span>
                <Input
                  type="number"
                  placeholder="0.00"
                  className="pl-7"
                  value={data.budgetType === "daily" ? data.dailyBudget : data.lifetimeBudget}
                  onChange={(e) =>
                    updateData(
                      data.budgetType === "daily"
                        ? { dailyBudget: e.target.value }
                        : { lifetimeBudget: e.target.value }
                    )
                  }
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bid Strategy */}
      <div className="space-y-2">
        <Label>Bid Strategy</Label>
        <Select value={data.bidStrategy} onValueChange={(v) => updateData({ bidStrategy: v })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {BID_STRATEGIES.map((b) => (
              <SelectItem key={b.value} value={b.value}>
                {b.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Schedule */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>Start Date</Label>
          <Input
            type="date"
            value={data.startDate}
            onChange={(e) => updateData({ startDate: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>End Date (optional)</Label>
          <Input
            type="date"
            value={data.endDate}
            onChange={(e) => updateData({ endDate: e.target.value })}
          />
        </div>
      </div>
    </div>
  )
}

/* ==========================================================================
   STEP 3 — AD SET
   ========================================================================== */

function StepAdSet() {
  const { data, updateData } = useWizard()
  const [locationInput, setLocationInput] = useState("")
  const [interestInput, setInterestInput] = useState("")
  const [langSearch, setLangSearch] = useState("")

  const addLocation = (loc: string) => {
    if (loc && !data.locations.includes(loc)) {
      updateData({ locations: [...data.locations, loc] })
    }
    setLocationInput("")
  }

  const removeLocation = (loc: string) => {
    updateData({ locations: data.locations.filter((l) => l !== loc) })
  }

  const addRegion = (countries: string[]) => {
    const merged = [...new Set([...data.locations, ...countries])]
    updateData({ locations: merged })
  }

  const addInterest = (interest: string) => {
    if (interest && !data.interests.includes(interest)) {
      updateData({ interests: [...data.interests, interest] })
    }
    setInterestInput("")
  }

  const removeInterest = (interest: string) => {
    updateData({ interests: data.interests.filter((i) => i !== interest) })
  }

  const toggleLanguage = (lang: string) => {
    const current = data.languages
    updateData({
      languages: current.includes(lang)
        ? current.filter((l) => l !== lang)
        : [...current, lang],
    })
  }

  const togglePlacement = (key: string) => {
    updateData({ placements: { ...data.placements, [key]: !data.placements[key] } })
  }

  const filteredLangs = LANGUAGES.filter((l) =>
    l.toLowerCase().includes(langSearch.toLowerCase())
  )

  const ages = Array.from({ length: 48 }, (_, i) => i + 18)

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-white">Ad Set Configuration</h2>
        <p className="text-sm text-gray-400">Define your audience, placements, and delivery optimization.</p>
      </div>

      {/* Ad Set Name */}
      <div className="space-y-2">
        <Label>Ad Set Name *</Label>
        <Input
          placeholder="e.g. US — 18-35 — Interest Targeting"
          value={data.adSetName}
          onChange={(e) => updateData({ adSetName: e.target.value })}
        />
      </div>

      {/* --- Targeting --- */}
      <div className="space-y-6 rounded-lg border border-gray-700 bg-gray-800/50 p-5">
        <h3 className="font-semibold text-white">Audience Targeting</h3>

        {/* Locations */}
        <div className="space-y-3">
          <Label>Locations</Label>
          <div className="flex gap-2">
            <Input
              placeholder="Type a country or city…"
              value={locationInput}
              onChange={(e) => setLocationInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  addLocation(locationInput.trim())
                }
              }}
              className="flex-1"
            />
            <Button variant="secondary" size="sm" onClick={() => addLocation(locationInput.trim())}>
              Add
            </Button>
          </div>
          <div className="flex flex-wrap gap-1">
            {REGION_PRESETS.map((r) => (
              <button
                key={r.id}
                onClick={() => addRegion(r.countries)}
                className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:border-blue-500 hover:text-blue-400"
              >
                + {r.label}
              </button>
            ))}
          </div>
          {data.locations.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.locations.map((loc) => (
                <Badge key={loc} variant="secondary" className="gap-1 pr-1">
                  {loc}
                  <button onClick={() => removeLocation(loc)} className="rounded-full p-0.5 hover:bg-gray-600">
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Age & Gender */}
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label>Min Age</Label>
            <Select value={String(data.ageMin)} onValueChange={(v) => updateData({ ageMin: Number(v) })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ages.map((a) => (
                  <SelectItem key={a} value={String(a)}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Max Age</Label>
            <Select value={String(data.ageMax)} onValueChange={(v) => updateData({ ageMax: Number(v) })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ages.map((a) => (
                  <SelectItem key={a} value={String(a)}>
                    {a === 65 ? "65+" : a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Gender</Label>
            <Select value={data.gender} onValueChange={(v) => updateData({ gender: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="male">Male</SelectItem>
                <SelectItem value="female">Female</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Languages */}
        <div className="space-y-2">
          <Label>Languages</Label>
          <Input
            placeholder="Search languages…"
            value={langSearch}
            onChange={(e) => setLangSearch(e.target.value)}
            className="mb-2"
          />
          <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
            {filteredLangs.map((lang) => {
              const selected = data.languages.includes(lang)
              return (
                <button
                  key={lang}
                  onClick={() => toggleLanguage(lang)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                    selected
                      ? "border-blue-500 bg-blue-600/10 text-blue-400"
                      : "border-gray-700 text-gray-400 hover:border-gray-600"
                  )}
                >
                  {selected && <Check className="mr-1 inline h-3 w-3" />}
                  {lang}
                </button>
              )
            })}
          </div>
        </div>

        {/* Interests */}
        <div className="space-y-3">
          <Label>Detailed Targeting (Interests & Behaviors)</Label>
          <div className="flex gap-2">
            <Input
              placeholder="Search interests, behaviors, demographics…"
              value={interestInput}
              onChange={(e) => setInterestInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  addInterest(interestInput.trim())
                }
              }}
              className="flex-1"
            />
            <Button variant="secondary" size="sm" onClick={() => addInterest(interestInput.trim())}>
              Add
            </Button>
          </div>
          {data.interests.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.interests.map((i) => (
                <Badge key={i} variant="secondary" className="gap-1 pr-1">
                  {i}
                  <button onClick={() => removeInterest(i)} className="rounded-full p-0.5 hover:bg-gray-600">
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* --- Placements --- */}
      <div className="space-y-4 rounded-lg border border-gray-700 bg-gray-800/50 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-white">Placements</h3>
            <p className="text-xs text-gray-400">Choose where your ads appear.</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Advantage+</span>
            <Switch
              checked={data.advantagePlacements}
              onCheckedChange={(v) => updateData({ advantagePlacements: v })}
            />
          </div>
        </div>

        {data.advantagePlacements ? (
          <div className="flex items-center gap-3 rounded-lg bg-blue-600/10 p-4">
            <Sparkles className="h-5 w-5 text-blue-400" />
            <div>
              <p className="text-sm font-medium text-blue-300">Advantage+ Placements Enabled</p>
              <p className="text-xs text-gray-400">
                Meta will automatically show your ads in the places most likely to drive results.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {PLACEMENT_GROUPS.map((group) => (
              <div key={group.platform} className="space-y-2">
                <div className="flex items-center gap-2">
                  <group.icon className="h-4 w-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-200">{group.platform}</span>
                </div>
                <div className="ml-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {group.placements.map((p) => {
                    const key = `${group.platform}_${p}`.toLowerCase().replace(/\s+/g, "_")
                    const checked = !!data.placements[key]
                    return (
                      <label key={key} className="flex cursor-pointer items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => togglePlacement(key)}
                          className="rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
                        />
                        {p}
                      </label>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* --- Budget & Schedule (ad set level) --- */}
      {data.budgetOptimization === "adset" && (
        <div className="space-y-4 rounded-lg border border-gray-700 bg-gray-800/50 p-5">
          <h3 className="font-semibold text-white">Budget & Schedule</h3>
          <div className="flex gap-3">
            <button
              onClick={() => updateData({ adSetBudgetType: "daily" })}
              className={cn(
                "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                data.adSetBudgetType === "daily"
                  ? "border-blue-500 bg-blue-600/10 text-blue-400"
                  : "border-gray-700 text-gray-400"
              )}
            >
              Daily Budget
            </button>
            <button
              onClick={() => updateData({ adSetBudgetType: "lifetime" })}
              className={cn(
                "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
                data.adSetBudgetType === "lifetime"
                  ? "border-blue-500 bg-blue-600/10 text-blue-400"
                  : "border-gray-700 text-gray-400"
              )}
            >
              Lifetime Budget
            </button>
          </div>
          <div className="space-y-2">
            <Label>{data.adSetBudgetType === "daily" ? "Daily Budget (USD)" : "Lifetime Budget (USD)"}</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">$</span>
              <Input
                type="number"
                placeholder="0.00"
                className="pl-7"
                value={data.adSetBudgetType === "daily" ? data.adSetDailyBudget : data.adSetLifetimeBudget}
                onChange={(e) =>
                  updateData(
                    data.adSetBudgetType === "daily"
                      ? { adSetDailyBudget: e.target.value }
                      : { adSetLifetimeBudget: e.target.value }
                  )
                }
              />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input
                type="date"
                value={data.adSetStartDate}
                onChange={(e) => updateData({ adSetStartDate: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input
                type="date"
                value={data.adSetEndDate}
                onChange={(e) => updateData({ adSetEndDate: e.target.value })}
              />
            </div>
          </div>
        </div>
      )}

      {/* --- Optimization --- */}
      <div className="space-y-4 rounded-lg border border-gray-700 bg-gray-800/50 p-5">
        <h3 className="font-semibold text-white">Optimization & Delivery</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Optimization Goal</Label>
            <Select value={data.optimizationGoal} onValueChange={(v) => updateData({ optimizationGoal: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OPTIMIZATION_GOALS.map((g) => (
                  <SelectItem key={g.value} value={g.value}>
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Billing Event</Label>
            <Select value={data.billingEvent} onValueChange={(v) => updateData({ billingEvent: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {BILLING_EVENTS.map((b) => (
                  <SelectItem key={b.value} value={b.value}>
                    {b.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ==========================================================================
   STEP 4 — AD CREATIVE
   ========================================================================== */

function StepAdCreative() {
  const { data, updateData } = useWizard()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFile = useCallback(
    (file: File) => {
      const url = URL.createObjectURL(file)
      updateData({ mediaUrl: url })
    },
    [updateData]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const formats = [
    { id: "single_image", label: "Single Image", icon: ImageIcon },
    { id: "single_video", label: "Single Video", icon: Film },
    { id: "carousel", label: "Carousel", icon: LayoutGrid },
  ]

  const ctaLabel = CTA_OPTIONS.find((c) => c.value === data.cta)?.label ?? "Learn More"

  return (
    <div className="grid gap-8 lg:grid-cols-5">
      {/* form */}
      <div className="space-y-6 lg:col-span-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Ad Creative</h2>
          <p className="text-sm text-gray-400">Design your ad with compelling visuals and copy.</p>
        </div>

        {/* Ad Name */}
        <div className="space-y-2">
          <Label>Ad Name *</Label>
          <Input
            placeholder="e.g. Summer Sale — Image 1"
            value={data.adName}
            onChange={(e) => updateData({ adName: e.target.value })}
          />
        </div>

        {/* Page Selection */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Facebook Page</Label>
            <Input
              placeholder="Select or enter Page ID"
              value={data.facebookPageId}
              onChange={(e) => updateData({ facebookPageId: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Instagram Account</Label>
            <Input
              placeholder="Select or enter account"
              value={data.instagramAccountId}
              onChange={(e) => updateData({ instagramAccountId: e.target.value })}
            />
          </div>
        </div>

        {/* Format */}
        <div className="space-y-3">
          <Label>Format</Label>
          <div className="flex gap-3">
            {formats.map((f) => {
              const selected = data.format === f.id
              return (
                <button
                  key={f.id}
                  onClick={() => updateData({ format: f.id })}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                    selected
                      ? "border-blue-500 bg-blue-600/10 text-blue-400 ring-2 ring-blue-500"
                      : "border-gray-700 text-gray-400 hover:border-gray-600"
                  )}
                >
                  <f.icon className="h-4 w-4" />
                  {f.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Media Upload */}
        <div className="space-y-2">
          <Label>Media</Label>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
              dragOver
                ? "border-blue-500 bg-blue-600/10"
                : data.mediaUrl
                ? "border-green-500/50 bg-green-600/5"
                : "border-gray-700 hover:border-gray-600"
            )}
          >
            {data.mediaUrl ? (
              <div className="relative">
                <img
                  src={data.mediaUrl}
                  alt="Preview"
                  className="max-h-48 rounded-lg object-contain"
                />
                <button
                  onClick={(e) => { e.stopPropagation(); updateData({ mediaUrl: "" }) }}
                  className="absolute -right-2 -top-2 rounded-full bg-gray-800 p-1 hover:bg-gray-700"
                >
                  <X className="h-4 w-4 text-gray-400" />
                </button>
              </div>
            ) : (
              <>
                <Upload className="mb-3 h-8 w-8 text-gray-500" />
                <p className="text-sm font-medium text-gray-300">
                  Drag & drop or click to upload
                </p>
                <p className="mt-1 text-xs text-gray-500">
                  PNG, JPG, MP4 up to 30MB
                </p>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleFile(file)
              }}
            />
          </div>
        </div>

        {/* Copy */}
        <div className="space-y-2">
          <Label>Primary Text *</Label>
          <textarea
            placeholder="Write the main body text for your ad…"
            value={data.primaryText}
            onChange={(e) => updateData({ primaryText: e.target.value })}
            rows={3}
            className="flex w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Headline *</Label>
            <Input
              placeholder="Catchy headline…"
              value={data.headline}
              onChange={(e) => updateData({ headline: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Input
              placeholder="Optional description…"
              value={data.description}
              onChange={(e) => updateData({ description: e.target.value })}
            />
          </div>
        </div>

        {/* CTA & URL */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Call to Action</Label>
            <Select value={data.cta} onValueChange={(v) => updateData({ cta: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CTA_OPTIONS.map((c) => (
                  <SelectItem key={c.value} value={c.value}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Website URL</Label>
            <Input
              placeholder="https://example.com"
              value={data.websiteUrl}
              onChange={(e) => updateData({ websiteUrl: e.target.value })}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Display Link (optional)</Label>
            <Input
              placeholder="example.com"
              value={data.displayLink}
              onChange={(e) => updateData({ displayLink: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>URL Parameters</Label>
            <Input
              placeholder="utm_source=facebook&utm_medium=cpc"
              value={data.urlParameters}
              onChange={(e) => updateData({ urlParameters: e.target.value })}
            />
          </div>
        </div>
      </div>

      {/* preview */}
      <div className="lg:col-span-2">
        <div className="sticky top-6 space-y-3">
          <h3 className="text-sm font-semibold text-gray-400">Ad Preview</h3>
          <div className="overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
            {/* Post header */}
            <div className="flex items-center gap-3 p-3">
              <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-violet-500" />
              <div>
                <p className="text-sm font-semibold text-white">
                  {data.facebookPageId || "Your Page"}
                </p>
                <p className="text-xs text-gray-500">Sponsored · 🌐</p>
              </div>
            </div>

            {/* Primary text */}
            <div className="px-3 pb-2">
              <p className="text-sm text-gray-200">
                {data.primaryText || "Your primary text will appear here…"}
              </p>
            </div>

            {/* Media */}
            <div className="aspect-video w-full bg-gray-800">
              {data.mediaUrl ? (
                <img src={data.mediaUrl} alt="Ad" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <ImageIcon className="h-12 w-12 text-gray-600" />
                </div>
              )}
            </div>

            {/* CTA bar */}
            <div className="flex items-center justify-between border-t border-gray-800 p-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-gray-500">
                  {data.displayLink || data.websiteUrl || "example.com"}
                </p>
                <p className="truncate text-sm font-semibold text-white">
                  {data.headline || "Your headline"}
                </p>
                {data.description && (
                  <p className="truncate text-xs text-gray-400">{data.description}</p>
                )}
              </div>
              <button className="ml-3 shrink-0 rounded bg-gray-700 px-3 py-1.5 text-xs font-semibold text-white">
                {ctaLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ==========================================================================
   STEP 5 — REVIEW
   ========================================================================== */

function StepReview() {
  const { data, goToStep } = useWizard()

  const objectiveLabel = OBJECTIVES.find((o) => o.id === data.objective)?.label ?? data.objective
  const bidLabel = BID_STRATEGIES.find((b) => b.value === data.bidStrategy)?.label ?? data.bidStrategy
  const optLabel = OPTIMIZATION_GOALS.find((o) => o.value === data.optimizationGoal)?.label ?? data.optimizationGoal
  const ctaLabel = CTA_OPTIONS.find((c) => c.value === data.cta)?.label ?? data.cta
  const formatLabel =
    data.format === "single_image" ? "Single Image" : data.format === "single_video" ? "Single Video" : "Carousel"

  const activePlacements = data.advantagePlacements
    ? "Advantage+ (Automatic)"
    : Object.entries(data.placements)
        .filter(([, v]) => v)
        .map(([k]) => k.replace(/_/g, " "))
        .join(", ") || "None selected"

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Review Your Campaign</h2>
        <p className="text-sm text-gray-400">Confirm everything looks good before publishing.</p>
      </div>

      {/* Campaign */}
      <ReviewSection title="Campaign" step={1} onEdit={() => goToStep(0)}>
        <ReviewRow label="Objective" value={objectiveLabel} />
        <ReviewRow label="Campaign Name" value={data.campaignName} />
        {data.specialCategories.length > 0 && (
          <ReviewRow
            label="Special Categories"
            value={data.specialCategories
              .map((c) => SPECIAL_CATEGORIES.find((s) => s.id === c)?.label ?? c)
              .join(", ")}
          />
        )}
        <ReviewRow label="Budget Optimization" value={data.budgetOptimization === "campaign" ? "Campaign Budget" : "Ad Set Budget"} />
        {data.budgetOptimization === "campaign" && (
          <ReviewRow
            label="Budget"
            value={
              data.budgetType === "daily"
                ? `$${data.dailyBudget || "0"}/day`
                : `$${data.lifetimeBudget || "0"} lifetime`
            }
          />
        )}
        <ReviewRow label="Bid Strategy" value={bidLabel} />
        {data.startDate && <ReviewRow label="Start Date" value={data.startDate} />}
        {data.endDate && <ReviewRow label="End Date" value={data.endDate} />}
      </ReviewSection>

      {/* Ad Set */}
      <ReviewSection title="Ad Set" step={3} onEdit={() => goToStep(2)}>
        <ReviewRow label="Ad Set Name" value={data.adSetName} />
        <ReviewRow label="Locations" value={data.locations.join(", ") || "Not specified"} />
        <ReviewRow label="Age" value={`${data.ageMin} – ${data.ageMax === 65 ? "65+" : data.ageMax}`} />
        <ReviewRow label="Gender" value={data.gender === "all" ? "All" : data.gender === "male" ? "Male" : "Female"} />
        {data.languages.length > 0 && <ReviewRow label="Languages" value={data.languages.join(", ")} />}
        {data.interests.length > 0 && <ReviewRow label="Interests" value={data.interests.join(", ")} />}
        <ReviewRow label="Placements" value={activePlacements} />
        <ReviewRow label="Optimization" value={optLabel} />
        <ReviewRow label="Billing Event" value={data.billingEvent === "impressions" ? "Impressions" : "Link Clicks"} />
      </ReviewSection>

      {/* Ad */}
      <ReviewSection title="Ad Creative" step={4} onEdit={() => goToStep(3)}>
        <ReviewRow label="Ad Name" value={data.adName} />
        <ReviewRow label="Format" value={formatLabel} />
        <ReviewRow label="Headline" value={data.headline} />
        <ReviewRow label="Primary Text" value={data.primaryText} />
        {data.description && <ReviewRow label="Description" value={data.description} />}
        <ReviewRow label="CTA" value={ctaLabel} />
        {data.websiteUrl && <ReviewRow label="Website URL" value={data.websiteUrl} />}
        {data.mediaUrl && (
          <div className="mt-3">
            <img src={data.mediaUrl} alt="Creative" className="h-32 rounded-lg object-cover" />
          </div>
        )}
      </ReviewSection>
    </div>
  )
}

function ReviewSection({
  title,
  step,
  onEdit,
  children,
}: {
  title: string
  step: number
  onEdit: () => void
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50">
      <div className="flex items-center justify-between border-b border-gray-700 px-5 py-3">
        <h3 className="font-semibold text-white">{title}</h3>
        <Button variant="ghost" size="sm" onClick={onEdit}>
          Edit
        </Button>
      </div>
      <div className="divide-y divide-gray-700/50 px-5">{children}</div>
    </div>
  )
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <span className="shrink-0 text-sm text-gray-400">{label}</span>
      <span className="text-right text-sm text-white">{value || "—"}</span>
    </div>
  )
}
