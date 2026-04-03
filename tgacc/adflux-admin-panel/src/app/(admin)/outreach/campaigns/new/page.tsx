"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { ArrowLeft, Plus, Trash2, Loader2, Megaphone } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"

interface ExistingSequence {
  id: string
  name: string
}

interface InlineStep {
  step_order: number
  delay_hours: number
  template_a: string
  template_b: string
  step_type: string
}

export default function NewCampaignPage() {
  const router = useRouter()
  const token = useApiToken()
  const { data: sequences } = useApi<ExistingSequence[]>("/outreach/sequences")

  // Form state
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [targetNiche, setTargetNiche] = useState("")
  const [dailySendCap, setDailySendCap] = useState(50)
  const [sendWindowStart, setSendWindowStart] = useState(9)
  const [sendWindowEnd, setSendWindowEnd] = useState(21)

  // Sequence selection
  const [sequenceMode, setSequenceMode] = useState<"existing" | "inline">("existing")
  const [selectedSequenceId, setSelectedSequenceId] = useState("")
  const [steps, setSteps] = useState<InlineStep[]>([])

  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const addStep = () => {
    setSteps(prev => [
      ...prev,
      {
        step_order: prev.length + 1,
        delay_hours: prev.length === 0 ? 0 : 24,
        template_a: "",
        template_b: "",
        step_type: "message",
      },
    ])
  }

  const removeStep = (index: number) => {
    setSteps(prev =>
      prev.filter((_, i) => i !== index).map((s, i) => ({ ...s, step_order: i + 1 }))
    )
  }

  const updateStep = (index: number, field: keyof InlineStep, value: string | number) => {
    setSteps(prev => prev.map((s, i) => i === index ? { ...s, [field]: value } : s))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    if (!name.trim()) { setFormError("Campaign name is required"); return }

    setSubmitting(true)
    setFormError(null)

    try {
      const body: Record<string, any> = {
        name: name.trim(),
        description: description.trim(),
        status: "draft",
        target_niche: targetNiche.trim(),
        daily_send_cap: dailySendCap,
        send_window_start: sendWindowStart,
        send_window_end: sendWindowEnd,
      }

      if (sequenceMode === "existing" && selectedSequenceId) {
        body.sequence_id = selectedSequenceId
      } else if (sequenceMode === "inline" && steps.length > 0) {
        body.steps = steps.map(s => ({
          step_order: s.step_order,
          delay_hours: s.delay_hours,
          template_a: s.template_a,
          template_b: s.template_b || undefined,
          step_type: s.step_type,
        }))
      }

      await apiFetch("/outreach/campaigns", token, {
        method: "POST",
        body: JSON.stringify(body),
      })
      router.push("/outreach/campaigns")
    } catch (err: any) {
      setFormError(err.message || "Failed to create campaign")
    } finally {
      setSubmitting(false)
    }
  }

  const hourOptions = Array.from({ length: 24 }, (_, i) => ({
    value: String(i),
    label: `${i}:00`,
  }))

  const sequenceOptions = [
    { value: "", label: "Select a sequence…" },
    ...(sequences ?? []).map(s => ({ value: s.id, label: s.name })),
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/outreach/campaigns">
          <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="h-6 w-6" /> New Campaign
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {formError && (
          <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{formError}</div>
        )}

        {/* Basic info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Campaign Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Name</label>
              <Input placeholder="Campaign name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Description</label>
              <textarea
                className="flex w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[80px]"
                placeholder="Campaign description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Target Niche</label>
              <Input placeholder="e.g. E-commerce, SaaS, Crypto" value={targetNiche} onChange={(e) => setTargetNiche(e.target.value)} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Daily Send Cap</label>
                <Input
                  type="number"
                  min={1}
                  max={1000}
                  value={dailySendCap}
                  onChange={(e) => setDailySendCap(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Send Window Start</label>
                <Select
                  value={String(sendWindowStart)}
                  onChange={(e) => setSendWindowStart(Number(e.target.value))}
                  options={hourOptions}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Send Window End</label>
                <Select
                  value={String(sendWindowEnd)}
                  onChange={(e) => setSendWindowEnd(Number(e.target.value))}
                  options={hourOptions}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Sequence section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Sequence</CardTitle>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={sequenceMode === "existing" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSequenceMode("existing")}
                >
                  Use Existing
                </Button>
                <Button
                  type="button"
                  variant={sequenceMode === "inline" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSequenceMode("inline")}
                >
                  Create Inline
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {sequenceMode === "existing" ? (
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Select Sequence</label>
                <Select
                  value={selectedSequenceId}
                  onChange={(e) => setSelectedSequenceId(e.target.value)}
                  options={sequenceOptions}
                />
              </div>
            ) : (
              <>
                {steps.length === 0 ? (
                  <p className="text-center py-6 text-muted-foreground">No steps added yet. Click &quot;Add Step&quot; to create your sequence.</p>
                ) : (
                  <div className="space-y-4">
                    {steps.map((step, idx) => (
                      <div key={idx} className="rounded-lg border border-border p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">Step {step.step_order}</span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeStep(idx)}
                            title="Remove step"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-muted-foreground mb-1 block">Delay (hours)</label>
                            <Input
                              type="number"
                              min={0}
                              value={step.delay_hours}
                              onChange={(e) => updateStep(idx, "delay_hours", Number(e.target.value))}
                            />
                          </div>
                          <div>
                            <label className="text-xs text-muted-foreground mb-1 block">Type</label>
                            <Select
                              value={step.step_type}
                              onChange={(e) => updateStep(idx, "step_type", e.target.value)}
                              options={[{ value: "message", label: "Message" }]}
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground mb-1 block">Template A</label>
                          <textarea
                            className="flex w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[80px]"
                            placeholder="Main message template…"
                            value={step.template_a}
                            onChange={(e) => updateStep(idx, "template_a", e.target.value)}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground mb-1 block">Template B (optional, for A/B testing)</label>
                          <textarea
                            className="flex w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[80px]"
                            placeholder="Alternative message template…"
                            value={step.template_b}
                            onChange={(e) => updateStep(idx, "template_b", e.target.value)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <Button type="button" variant="outline" onClick={addStep} className="w-full">
                  <Plus className="h-4 w-4 mr-2" /> Add Step
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex gap-3">
          <Link href="/outreach/campaigns" className="flex-1">
            <Button type="button" variant="outline" className="w-full">Cancel</Button>
          </Link>
          <Button type="submit" className="flex-1" disabled={submitting}>
            {submitting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Creating…</> : "Create Campaign"}
          </Button>
        </div>
      </form>
    </div>
  )
}
