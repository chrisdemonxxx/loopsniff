"use client"

import { WizardProvider } from "./wizard-context"

export default function CreateCampaignLayout({ children }: { children: React.ReactNode }) {
  return <WizardProvider>{children}</WizardProvider>
}
