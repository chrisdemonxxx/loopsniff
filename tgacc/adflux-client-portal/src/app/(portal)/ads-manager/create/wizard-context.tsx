"use client"

import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

export interface WizardData {
  // Step 1
  objective: string
  // Step 2
  campaignName: string
  specialCategories: string[]
  budgetOptimization: "campaign" | "adset"
  dailyBudget: string
  lifetimeBudget: string
  budgetType: "daily" | "lifetime"
  bidStrategy: string
  startDate: string
  endDate: string
  // Step 3
  adSetName: string
  locations: string[]
  ageMin: number
  ageMax: number
  gender: string
  languages: string[]
  interests: string[]
  placements: Record<string, boolean>
  advantagePlacements: boolean
  adSetDailyBudget: string
  adSetLifetimeBudget: string
  adSetBudgetType: "daily" | "lifetime"
  optimizationGoal: string
  billingEvent: string
  adSetStartDate: string
  adSetEndDate: string
  // Step 4
  adName: string
  format: string
  primaryText: string
  headline: string
  description: string
  cta: string
  websiteUrl: string
  displayLink: string
  urlParameters: string
  mediaUrl: string
  facebookPageId: string
  instagramAccountId: string
}

const defaultData: WizardData = {
  objective: "",
  campaignName: "",
  specialCategories: [],
  budgetOptimization: "campaign",
  dailyBudget: "",
  lifetimeBudget: "",
  budgetType: "daily",
  bidStrategy: "lowest_cost",
  startDate: "",
  endDate: "",
  adSetName: "",
  locations: [],
  ageMin: 18,
  ageMax: 65,
  gender: "all",
  languages: [],
  interests: [],
  placements: {},
  advantagePlacements: true,
  adSetDailyBudget: "",
  adSetLifetimeBudget: "",
  adSetBudgetType: "daily",
  optimizationGoal: "link_clicks",
  billingEvent: "impressions",
  adSetStartDate: "",
  adSetEndDate: "",
  adName: "",
  format: "single_image",
  primaryText: "",
  headline: "",
  description: "",
  cta: "learn_more",
  websiteUrl: "",
  displayLink: "",
  urlParameters: "",
  mediaUrl: "",
  facebookPageId: "",
  instagramAccountId: "",
}

interface WizardContextType {
  data: WizardData
  step: number
  updateData: (updates: Partial<WizardData>) => void
  nextStep: () => void
  prevStep: () => void
  goToStep: (step: number) => void
  canProceed: boolean
}

const WizardContext = createContext<WizardContextType | null>(null)

export function WizardProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<WizardData>(defaultData)
  const [step, setStep] = useState(0)

  const updateData = useCallback((updates: Partial<WizardData>) => {
    setData((prev) => ({ ...prev, ...updates }))
  }, [])

  const canProceed = (() => {
    switch (step) {
      case 0:
        return !!data.objective
      case 1:
        return !!data.campaignName
      case 2:
        return !!data.adSetName
      case 3:
        return !!data.adName && !!data.primaryText && !!data.headline
      case 4:
        return true
      default:
        return false
    }
  })()

  const nextStep = useCallback(() => {
    setStep((s) => Math.min(s + 1, 4))
  }, [])

  const prevStep = useCallback(() => {
    setStep((s) => Math.max(s - 1, 0))
  }, [])

  const goToStep = useCallback((target: number) => {
    if (target >= 0 && target <= 4) setStep(target)
  }, [])

  return (
    <WizardContext.Provider value={{ data, step, updateData, nextStep, prevStep, goToStep, canProceed }}>
      {children}
    </WizardContext.Provider>
  )
}

export function useWizard() {
  const ctx = useContext(WizardContext)
  if (!ctx) throw new Error("useWizard must be used within WizardProvider")
  return ctx
}
