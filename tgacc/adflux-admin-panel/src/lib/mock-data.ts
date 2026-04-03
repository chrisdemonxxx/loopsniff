// Types
export type ClientPlan = 'starter' | 'growth' | 'premium' | 'enterprise' | 'custom'
export type ClientStatus = 'active' | 'suspended' | 'pending' | 'churned'
export type AccountPlatform = 'facebook' | 'google' | 'tiktok' | 'snapchat'
export type AccountStatus = 'active' | 'banned' | 'limited' | 'pending' | 'disabled'
export type TransactionType = 'deposit' | 'commission' | 'setup_fee' | 'monthly_fee' | 'refund' | 'transfer'
export type TransactionStatus = 'completed' | 'pending' | 'failed'
export type LeadStage = 'new' | 'contacted' | 'replied' | 'engaged' | 'qualified' | 'hot' | 'payment_sent' | 'converted' | 'onboarded'
export type AdminRole = 'super_admin' | 'admin' | 'support' | 'viewer'

export interface Client {
  id: string
  name: string
  company: string
  email: string
  telegram: string
  plan: ClientPlan
  niche: string
  status: ClientStatus
  accountCount: number
  balance: number
  lastActivity: string
  createdAt: string
}

export interface AdAccount {
  id: string
  clientId: string
  clientName: string
  platform: AccountPlatform
  accountId: string
  name: string
  status: AccountStatus
  balance: number
  spend30d: number
  dailyLimit: number
  createdAt: string
}

export interface Transaction {
  id: string
  clientId: string
  clientName: string
  type: TransactionType
  adAmount: number
  commission: number
  cryptoAmount: number
  currency: string
  status: TransactionStatus
  date: string
  description: string
}

export interface Lead {
  id: string
  username: string
  source: string
  bantScore: number
  stage: LeadStage
  lastContact: string
  assignedTo: string
  notes: string
  company: string
  budget: string
}

export interface FunnelStage {
  stage: LeadStage
  label: string
  count: number
  conversionRate: number
}

export interface Activity {
  id: string
  type: string
  message: string
  timestamp: string
  user: string
}

export interface BotConversation {
  id: string
  username: string
  lastMessage: string
  lastMessageTime: string
  unreadCount: number
  tags: string[]
  messages: BotMessage[]
}

export interface BotMessage {
  id: string
  sender: 'user' | 'bot' | 'admin'
  text: string
  timestamp: string
}

export interface AdminUser {
  id: string
  name: string
  email: string
  role: AdminRole
  lastLogin: string
  status: 'active' | 'inactive'
}

// Mock Data

export const clients: Client[] = [
  {
    id: 'c1',
    name: 'Marcus Chen',
    company: 'Digital Spark Agency',
    email: 'marcus@digitalspark.io',
    telegram: '@marcuschen',
    plan: 'premium',
    niche: 'E-commerce',
    status: 'active',
    accountCount: 4,
    balance: 12500,
    lastActivity: '2025-01-15T10:30:00Z',
    createdAt: '2024-06-15T00:00:00Z',
  },
  {
    id: 'c2',
    name: 'Sarah Williams',
    company: 'GrowthMax Media',
    email: 'sarah@growthmax.co',
    telegram: '@sarahgm',
    plan: 'enterprise',
    niche: 'SaaS',
    status: 'active',
    accountCount: 3,
    balance: 45000,
    lastActivity: '2025-01-15T08:15:00Z',
    createdAt: '2024-03-20T00:00:00Z',
  },
  {
    id: 'c3',
    name: 'Jake Torres',
    company: 'AdRocket',
    email: 'jake@adrocket.com',
    telegram: '@jaketorres',
    plan: 'growth',
    niche: 'Dropshipping',
    status: 'active',
    accountCount: 2,
    balance: 3200,
    lastActivity: '2025-01-14T16:45:00Z',
    createdAt: '2024-09-01T00:00:00Z',
  },
  {
    id: 'c4',
    name: 'Emily Park',
    company: 'Nova Digital',
    email: 'emily@novadigital.co',
    telegram: '@emilypark',
    plan: 'starter',
    niche: 'Lead Gen',
    status: 'suspended',
    accountCount: 1,
    balance: 0,
    lastActivity: '2025-01-10T12:00:00Z',
    createdAt: '2024-11-10T00:00:00Z',
  },
  {
    id: 'c5',
    name: 'Ryan Okafor',
    company: 'Apex Ads',
    email: 'ryan@apexads.net',
    telegram: '@ryanokafor',
    plan: 'custom',
    niche: 'Crypto/Web3',
    status: 'active',
    accountCount: 2,
    balance: 28000,
    lastActivity: '2025-01-15T11:00:00Z',
    createdAt: '2024-01-05T00:00:00Z',
  },
]

export const adAccounts: AdAccount[] = [
  { id: 'a1', clientId: 'c1', clientName: 'Marcus Chen', platform: 'facebook', accountId: 'FB-28491', name: 'MC E-com Main', status: 'active', balance: 5000, spend30d: 18500, dailyLimit: 1000, createdAt: '2024-06-20T00:00:00Z' },
  { id: 'a2', clientId: 'c1', clientName: 'Marcus Chen', platform: 'facebook', accountId: 'FB-28492', name: 'MC E-com Scale', status: 'active', balance: 3500, spend30d: 12000, dailyLimit: 800, createdAt: '2024-08-15T00:00:00Z' },
  { id: 'a3', clientId: 'c1', clientName: 'Marcus Chen', platform: 'google', accountId: 'GG-71823', name: 'MC Google Shopping', status: 'active', balance: 2000, spend30d: 8000, dailyLimit: 500, createdAt: '2024-10-01T00:00:00Z' },
  { id: 'a4', clientId: 'c1', clientName: 'Marcus Chen', platform: 'tiktok', accountId: 'TT-55102', name: 'MC TikTok Ads', status: 'limited', balance: 2000, spend30d: 4500, dailyLimit: 300, createdAt: '2024-11-20T00:00:00Z' },
  { id: 'a5', clientId: 'c2', clientName: 'Sarah Williams', platform: 'facebook', accountId: 'FB-39201', name: 'GM SaaS Primary', status: 'active', balance: 20000, spend30d: 35000, dailyLimit: 2000, createdAt: '2024-03-25T00:00:00Z' },
  { id: 'a6', clientId: 'c2', clientName: 'Sarah Williams', platform: 'google', accountId: 'GG-82910', name: 'GM Google Search', status: 'active', balance: 15000, spend30d: 22000, dailyLimit: 1500, createdAt: '2024-05-10T00:00:00Z' },
  { id: 'a7', clientId: 'c2', clientName: 'Sarah Williams', platform: 'facebook', accountId: 'FB-39202', name: 'GM Retargeting', status: 'banned', balance: 10000, spend30d: 0, dailyLimit: 1000, createdAt: '2024-07-01T00:00:00Z' },
  { id: 'a8', clientId: 'c3', clientName: 'Jake Torres', platform: 'facebook', accountId: 'FB-45601', name: 'AR Dropship Main', status: 'active', balance: 2000, spend30d: 6500, dailyLimit: 500, createdAt: '2024-09-05T00:00:00Z' },
  { id: 'a9', clientId: 'c3', clientName: 'Jake Torres', platform: 'tiktok', accountId: 'TT-66201', name: 'AR TikTok Scale', status: 'active', balance: 1200, spend30d: 3200, dailyLimit: 300, createdAt: '2024-10-15T00:00:00Z' },
  { id: 'a10', clientId: 'c4', clientName: 'Emily Park', platform: 'facebook', accountId: 'FB-52301', name: 'ND Lead Gen', status: 'banned', balance: 0, spend30d: 0, dailyLimit: 200, createdAt: '2024-11-15T00:00:00Z' },
  { id: 'a11', clientId: 'c5', clientName: 'Ryan Okafor', platform: 'facebook', accountId: 'FB-61001', name: 'AA Crypto Main', status: 'active', balance: 18000, spend30d: 28000, dailyLimit: 2000, createdAt: '2024-01-10T00:00:00Z' },
  { id: 'a12', clientId: 'c5', clientName: 'Ryan Okafor', platform: 'snapchat', accountId: 'SC-18201', name: 'AA Snap Ads', status: 'active', balance: 10000, spend30d: 9500, dailyLimit: 800, createdAt: '2024-04-20T00:00:00Z' },
]

export const transactions: Transaction[] = [
  { id: 't1', clientId: 'c1', clientName: 'Marcus Chen', type: 'deposit', adAmount: 5000, commission: 500, cryptoAmount: 0.082, currency: 'BTC', status: 'completed', date: '2025-01-15T10:30:00Z', description: 'Account top-up FB-28491' },
  { id: 't2', clientId: 'c2', clientName: 'Sarah Williams', type: 'deposit', adAmount: 20000, commission: 1600, cryptoAmount: 32.5, currency: 'ETH', status: 'completed', date: '2025-01-14T14:20:00Z', description: 'Monthly deposit' },
  { id: 't3', clientId: 'c1', clientName: 'Marcus Chen', type: 'commission', adAmount: 0, commission: 250, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-13T09:00:00Z', description: 'Weekly commission' },
  { id: 't4', clientId: 'c3', clientName: 'Jake Torres', type: 'deposit', adAmount: 2000, commission: 200, cryptoAmount: 3.1, currency: 'ETH', status: 'completed', date: '2025-01-13T11:30:00Z', description: 'Account top-up FB-45601' },
  { id: 't5', clientId: 'c5', clientName: 'Ryan Okafor', type: 'deposit', adAmount: 15000, commission: 1200, cryptoAmount: 0.24, currency: 'BTC', status: 'completed', date: '2025-01-12T16:45:00Z', description: 'Bulk deposit' },
  { id: 't6', clientId: 'c2', clientName: 'Sarah Williams', type: 'setup_fee', adAmount: 0, commission: 500, cryptoAmount: 0.75, currency: 'ETH', status: 'completed', date: '2025-01-12T10:00:00Z', description: 'New account setup' },
  { id: 't7', clientId: 'c4', clientName: 'Emily Park', type: 'refund', adAmount: -1000, commission: -100, cryptoAmount: -1.5, currency: 'ETH', status: 'completed', date: '2025-01-11T14:30:00Z', description: 'Banned account refund' },
  { id: 't8', clientId: 'c1', clientName: 'Marcus Chen', type: 'monthly_fee', adAmount: 0, commission: 150, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-10T00:00:00Z', description: 'January monthly fee' },
  { id: 't9', clientId: 'c2', clientName: 'Sarah Williams', type: 'monthly_fee', adAmount: 0, commission: 300, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-10T00:00:00Z', description: 'January monthly fee' },
  { id: 't10', clientId: 'c3', clientName: 'Jake Torres', type: 'monthly_fee', adAmount: 0, commission: 100, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-10T00:00:00Z', description: 'January monthly fee' },
  { id: 't11', clientId: 'c5', clientName: 'Ryan Okafor', type: 'deposit', adAmount: 10000, commission: 800, cryptoAmount: 0.15, currency: 'BTC', status: 'completed', date: '2025-01-09T13:20:00Z', description: 'Account top-up' },
  { id: 't12', clientId: 'c1', clientName: 'Marcus Chen', type: 'deposit', adAmount: 3000, commission: 300, cryptoAmount: 4.5, currency: 'ETH', status: 'completed', date: '2025-01-08T10:45:00Z', description: 'Account top-up' },
  { id: 't13', clientId: 'c2', clientName: 'Sarah Williams', type: 'transfer', adAmount: 5000, commission: 0, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-07T15:30:00Z', description: 'Transfer from banned account' },
  { id: 't14', clientId: 'c3', clientName: 'Jake Torres', type: 'deposit', adAmount: 1500, commission: 150, cryptoAmount: 2.2, currency: 'ETH', status: 'pending', date: '2025-01-07T09:00:00Z', description: 'Pending deposit' },
  { id: 't15', clientId: 'c5', clientName: 'Ryan Okafor', type: 'commission', adAmount: 0, commission: 400, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-06T12:00:00Z', description: 'Weekly commission' },
  { id: 't16', clientId: 'c1', clientName: 'Marcus Chen', type: 'deposit', adAmount: 4000, commission: 400, cryptoAmount: 0.06, currency: 'BTC', status: 'completed', date: '2025-01-05T14:15:00Z', description: 'Account top-up' },
  { id: 't17', clientId: 'c2', clientName: 'Sarah Williams', type: 'deposit', adAmount: 25000, commission: 2000, cryptoAmount: 37.5, currency: 'ETH', status: 'completed', date: '2025-01-04T11:30:00Z', description: 'Large deposit' },
  { id: 't18', clientId: 'c4', clientName: 'Emily Park', type: 'setup_fee', adAmount: 0, commission: 200, cryptoAmount: 0.3, currency: 'ETH', status: 'completed', date: '2025-01-03T10:00:00Z', description: 'Initial setup fee' },
  { id: 't19', clientId: 'c5', clientName: 'Ryan Okafor', type: 'deposit', adAmount: 8000, commission: 640, cryptoAmount: 0.12, currency: 'BTC', status: 'completed', date: '2025-01-02T16:00:00Z', description: 'New year deposit' },
  { id: 't20', clientId: 'c1', clientName: 'Marcus Chen', type: 'commission', adAmount: 0, commission: 350, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2025-01-01T00:00:00Z', description: 'Monthly commission' },
  { id: 't21', clientId: 'c3', clientName: 'Jake Torres', type: 'deposit', adAmount: 1000, commission: 100, cryptoAmount: 1.5, currency: 'ETH', status: 'failed', date: '2024-12-30T10:00:00Z', description: 'Failed deposit' },
  { id: 't22', clientId: 'c2', clientName: 'Sarah Williams', type: 'deposit', adAmount: 15000, commission: 1200, cryptoAmount: 22.5, currency: 'ETH', status: 'completed', date: '2024-12-28T14:00:00Z', description: 'End of month deposit' },
  { id: 't23', clientId: 'c5', clientName: 'Ryan Okafor', type: 'monthly_fee', adAmount: 0, commission: 500, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2024-12-28T00:00:00Z', description: 'December monthly fee' },
  { id: 't24', clientId: 'c1', clientName: 'Marcus Chen', type: 'deposit', adAmount: 6000, commission: 600, cryptoAmount: 0.09, currency: 'BTC', status: 'completed', date: '2024-12-26T11:00:00Z', description: 'Holiday top-up' },
  { id: 't25', clientId: 'c4', clientName: 'Emily Park', type: 'deposit', adAmount: 1000, commission: 100, cryptoAmount: 1.5, currency: 'ETH', status: 'completed', date: '2024-12-24T09:00:00Z', description: 'Initial deposit' },
  { id: 't26', clientId: 'c2', clientName: 'Sarah Williams', type: 'commission', adAmount: 0, commission: 800, cryptoAmount: 0, currency: 'USD', status: 'completed', date: '2024-12-22T12:00:00Z', description: 'Bi-weekly commission' },
  { id: 't27', clientId: 'c3', clientName: 'Jake Torres', type: 'deposit', adAmount: 2500, commission: 250, cryptoAmount: 3.75, currency: 'ETH', status: 'completed', date: '2024-12-20T15:00:00Z', description: 'Account top-up' },
  { id: 't28', clientId: 'c5', clientName: 'Ryan Okafor', type: 'deposit', adAmount: 12000, commission: 960, cryptoAmount: 0.18, currency: 'BTC', status: 'completed', date: '2024-12-18T13:00:00Z', description: 'Large deposit' },
  { id: 't29', clientId: 'c1', clientName: 'Marcus Chen', type: 'setup_fee', adAmount: 0, commission: 300, cryptoAmount: 0.45, currency: 'ETH', status: 'completed', date: '2024-12-16T10:00:00Z', description: 'New TikTok account setup' },
  { id: 't30', clientId: 'c2', clientName: 'Sarah Williams', type: 'deposit', adAmount: 18000, commission: 1440, cryptoAmount: 27, currency: 'ETH', status: 'completed', date: '2024-12-15T14:00:00Z', description: 'Mid-month deposit' },
]

export const funnelData: FunnelStage[] = [
  { stage: 'new', label: 'New', count: 245, conversionRate: 100 },
  { stage: 'contacted', label: 'Contacted', count: 180, conversionRate: 73.5 },
  { stage: 'replied', label: 'Replied', count: 95, conversionRate: 52.8 },
  { stage: 'engaged', label: 'Engaged', count: 68, conversionRate: 71.6 },
  { stage: 'qualified', label: 'Qualified', count: 42, conversionRate: 61.8 },
  { stage: 'hot', label: 'Hot', count: 28, conversionRate: 66.7 },
  { stage: 'payment_sent', label: 'Payment Sent', count: 18, conversionRate: 64.3 },
  { stage: 'converted', label: 'Converted', count: 15, conversionRate: 83.3 },
  { stage: 'onboarded', label: 'Onboarded', count: 12, conversionRate: 80.0 },
]

export const leads: Lead[] = [
  { id: 'l1', username: '@alex_media', source: 'Telegram', bantScore: 85, stage: 'hot', lastContact: '2025-01-15T09:00:00Z', assignedTo: 'Admin', notes: 'Ready to convert, needs pricing', company: 'Alex Media LLC', budget: '$5k-10k/mo' },
  { id: 'l2', username: '@dropship_king', source: 'Instagram', bantScore: 72, stage: 'qualified', lastContact: '2025-01-14T16:00:00Z', assignedTo: 'Admin', notes: 'Interested in FB accounts', company: 'DropKing Stores', budget: '$2k-5k/mo' },
  { id: 'l3', username: '@sarah_ads', source: 'Referral', bantScore: 90, stage: 'payment_sent', lastContact: '2025-01-15T11:00:00Z', assignedTo: 'Admin', notes: 'Payment confirmed, setting up', company: 'Sarah Ads Co', budget: '$10k+/mo' },
  { id: 'l4', username: '@growth_hacker', source: 'Twitter', bantScore: 45, stage: 'contacted', lastContact: '2025-01-13T10:00:00Z', assignedTo: 'Support', notes: 'Initial outreach sent', company: 'GH Digital', budget: 'Unknown' },
  { id: 'l5', username: '@ninja_trader', source: 'Telegram', bantScore: 68, stage: 'engaged', lastContact: '2025-01-14T14:00:00Z', assignedTo: 'Admin', notes: 'Asking about crypto niche policy', company: 'Ninja Trading', budget: '$3k-5k/mo' },
  { id: 'l6', username: '@ecom_pro', source: 'Website', bantScore: 55, stage: 'replied', lastContact: '2025-01-12T09:00:00Z', assignedTo: 'Support', notes: 'Wants to know about pricing', company: 'EcomPro LLC', budget: '$1k-3k/mo' },
  { id: 'l7', username: '@brand_builder', source: 'LinkedIn', bantScore: 78, stage: 'qualified', lastContact: '2025-01-14T13:00:00Z', assignedTo: 'Admin', notes: 'Enterprise client potential', company: 'BrandBuilder Inc', budget: '$10k+/mo' },
  { id: 'l8', username: '@ad_master99', source: 'Telegram', bantScore: 35, stage: 'new', lastContact: '2025-01-15T08:00:00Z', assignedTo: 'Unassigned', notes: 'New lead from group', company: 'Unknown', budget: 'Unknown' },
  { id: 'l9', username: '@media_buy_co', source: 'Referral', bantScore: 82, stage: 'hot', lastContact: '2025-01-15T10:00:00Z', assignedTo: 'Admin', notes: 'Referred by Marcus Chen', company: 'MediaBuy Co', budget: '$5k-10k/mo' },
  { id: 'l10', username: '@scale_ads', source: 'Instagram', bantScore: 60, stage: 'engaged', lastContact: '2025-01-13T15:00:00Z', assignedTo: 'Support', notes: 'Comparing with competitors', company: 'ScaleAds Agency', budget: '$2k-5k/mo' },
  { id: 'l11', username: '@digital_nomad', source: 'Twitter', bantScore: 42, stage: 'contacted', lastContact: '2025-01-12T11:00:00Z', assignedTo: 'Support', notes: 'Freelancer, small budget', company: 'Freelance', budget: '$500-1k/mo' },
  { id: 'l12', username: '@roi_agency', source: 'Website', bantScore: 88, stage: 'converted', lastContact: '2025-01-11T14:00:00Z', assignedTo: 'Admin', notes: 'Just converted, onboarding', company: 'ROI Agency', budget: '$8k-15k/mo' },
  { id: 'l13', username: '@click_master', source: 'Telegram', bantScore: 50, stage: 'replied', lastContact: '2025-01-10T16:00:00Z', assignedTo: 'Support', notes: 'Slow to respond', company: 'ClickMaster', budget: '$1k-2k/mo' },
  { id: 'l14', username: '@performance_mk', source: 'LinkedIn', bantScore: 75, stage: 'qualified', lastContact: '2025-01-14T09:00:00Z', assignedTo: 'Admin', notes: 'Agency with multiple clients', company: 'Performance MK', budget: '$5k-10k/mo' },
  { id: 'l15', username: '@viral_ads', source: 'Referral', bantScore: 65, stage: 'engaged', lastContact: '2025-01-13T12:00:00Z', assignedTo: 'Admin', notes: 'Interested in TikTok accounts', company: 'ViralAds', budget: '$2k-5k/mo' },
  { id: 'l16', username: '@ad_wizard', source: 'Telegram', bantScore: 30, stage: 'new', lastContact: '2025-01-15T07:00:00Z', assignedTo: 'Unassigned', notes: 'Cold lead', company: 'Unknown', budget: 'Unknown' },
  { id: 'l17', username: '@boost_digital', source: 'Instagram', bantScore: 58, stage: 'contacted', lastContact: '2025-01-11T10:00:00Z', assignedTo: 'Support', notes: 'Follow-up needed', company: 'Boost Digital', budget: '$1k-3k/mo' },
  { id: 'l18', username: '@top_funnel', source: 'Website', bantScore: 92, stage: 'onboarded', lastContact: '2025-01-09T13:00:00Z', assignedTo: 'Admin', notes: 'Fully onboarded enterprise client', company: 'TopFunnel Corp', budget: '$15k+/mo' },
  { id: 'l19', username: '@ppc_labs', source: 'Referral', bantScore: 70, stage: 'hot', lastContact: '2025-01-14T15:00:00Z', assignedTo: 'Admin', notes: 'Scheduling setup call', company: 'PPC Labs', budget: '$3k-8k/mo' },
  { id: 'l20', username: '@startup_ads', source: 'Twitter', bantScore: 40, stage: 'new', lastContact: '2025-01-15T06:00:00Z', assignedTo: 'Unassigned', notes: 'Startup looking for options', company: 'TechStart Inc', budget: '$500-1k/mo' },
]

// Generate 30 days of revenue data
export const revenueData = Array.from({ length: 30 }, (_, i) => {
  const date = new Date('2024-12-17')
  date.setDate(date.getDate() + i)
  const base = 2000 + Math.random() * 3000
  return {
    date: date.toISOString().split('T')[0],
    revenue: Math.round(base),
    commission: Math.round(base * 0.08),
    deposits: Math.round(base * 0.85),
    fees: Math.round(base * 0.07),
  }
})

export const recentActivity: Activity[] = [
  { id: 'act1', type: 'deposit', message: 'Marcus Chen deposited $5,000 via BTC', timestamp: '2025-01-15T10:30:00Z', user: 'system' },
  { id: 'act2', type: 'account', message: 'New FB account created for Sarah Williams', timestamp: '2025-01-15T09:15:00Z', user: 'Admin' },
  { id: 'act3', type: 'alert', message: 'Account FB-39202 banned - Sarah Williams', timestamp: '2025-01-15T08:00:00Z', user: 'system' },
  { id: 'act4', type: 'lead', message: 'Lead @alex_media moved to Hot stage', timestamp: '2025-01-15T07:30:00Z', user: 'Admin' },
  { id: 'act5', type: 'client', message: 'Emily Park account suspended', timestamp: '2025-01-14T18:00:00Z', user: 'Admin' },
  { id: 'act6', type: 'deposit', message: 'Sarah Williams deposited $20,000 via ETH', timestamp: '2025-01-14T14:20:00Z', user: 'system' },
  { id: 'act7', type: 'outreach', message: 'Outreach batch sent to 15 new leads', timestamp: '2025-01-14T12:00:00Z', user: 'Admin' },
  { id: 'act8', type: 'account', message: 'TikTok account TT-55102 flagged as limited', timestamp: '2025-01-14T10:30:00Z', user: 'system' },
  { id: 'act9', type: 'lead', message: 'Lead @sarah_ads payment confirmed', timestamp: '2025-01-14T09:00:00Z', user: 'system' },
  { id: 'act10', type: 'deposit', message: 'Ryan Okafor deposited $15,000 via BTC', timestamp: '2025-01-12T16:45:00Z', user: 'system' },
]

export const escalations = [
  { id: 'e1', title: 'Banned account FB-39202 needs replacement', client: 'Sarah Williams', priority: 'high' as const, createdAt: '2025-01-15T08:00:00Z' },
  { id: 'e2', title: 'Client requesting refund for downtime', client: 'Emily Park', priority: 'medium' as const, createdAt: '2025-01-14T16:00:00Z' },
  { id: 'e3', title: 'TikTok account spending limited', client: 'Marcus Chen', priority: 'low' as const, createdAt: '2025-01-14T10:30:00Z' },
]

export const botConversations: BotConversation[] = [
  {
    id: 'conv1',
    username: 'Marcus Chen',
    lastMessage: 'Thanks, the new account is working great!',
    lastMessageTime: '2025-01-15T10:30:00Z',
    unreadCount: 0,
    tags: ['client', 'premium'],
    messages: [
      { id: 'm1', sender: 'user', text: 'Hey, I need a new FB account set up', timestamp: '2025-01-15T09:00:00Z' },
      { id: 'm2', sender: 'bot', text: 'Hi Marcus! I can help with that. What niche will this account be for?', timestamp: '2025-01-15T09:01:00Z' },
      { id: 'm3', sender: 'user', text: 'E-commerce, same as my others', timestamp: '2025-01-15T09:05:00Z' },
      { id: 'm4', sender: 'admin', text: 'Setting up now. Should be ready in 2 hours.', timestamp: '2025-01-15T09:15:00Z' },
      { id: 'm5', sender: 'user', text: 'Thanks, the new account is working great!', timestamp: '2025-01-15T10:30:00Z' },
    ],
  },
  {
    id: 'conv2',
    username: 'Sarah Williams',
    lastMessage: 'When will my replacement account be ready?',
    lastMessageTime: '2025-01-15T08:30:00Z',
    unreadCount: 2,
    tags: ['client', 'enterprise', 'escalation'],
    messages: [
      { id: 'm6', sender: 'user', text: 'My account FB-39202 just got banned!', timestamp: '2025-01-15T07:45:00Z' },
      { id: 'm7', sender: 'bot', text: 'I\'m sorry to hear that. Let me escalate this to the team immediately.', timestamp: '2025-01-15T07:46:00Z' },
      { id: 'm8', sender: 'user', text: 'I have $10k balance in that account', timestamp: '2025-01-15T08:00:00Z' },
      { id: 'm9', sender: 'user', text: 'When will my replacement account be ready?', timestamp: '2025-01-15T08:30:00Z' },
    ],
  },
  {
    id: 'conv3',
    username: 'Jake Torres',
    lastMessage: 'Can I increase my daily limit?',
    lastMessageTime: '2025-01-14T16:45:00Z',
    unreadCount: 1,
    tags: ['client', 'growth'],
    messages: [
      { id: 'm10', sender: 'user', text: 'Hi, my ads are performing well', timestamp: '2025-01-14T16:30:00Z' },
      { id: 'm11', sender: 'bot', text: 'That\'s great to hear! How can I help?', timestamp: '2025-01-14T16:31:00Z' },
      { id: 'm12', sender: 'user', text: 'Can I increase my daily limit?', timestamp: '2025-01-14T16:45:00Z' },
    ],
  },
  {
    id: 'conv4',
    username: '@alex_media',
    lastMessage: 'What plans do you offer?',
    lastMessageTime: '2025-01-15T09:00:00Z',
    unreadCount: 3,
    tags: ['lead', 'hot'],
    messages: [
      { id: 'm13', sender: 'user', text: 'Hi, I heard about your service from a friend', timestamp: '2025-01-15T08:45:00Z' },
      { id: 'm14', sender: 'bot', text: 'Welcome! We provide premium ad accounts for media buyers. What platforms are you interested in?', timestamp: '2025-01-15T08:46:00Z' },
      { id: 'm15', sender: 'user', text: 'Facebook and TikTok mainly', timestamp: '2025-01-15T08:50:00Z' },
      { id: 'm16', sender: 'user', text: 'What plans do you offer?', timestamp: '2025-01-15T09:00:00Z' },
    ],
  },
  {
    id: 'conv5',
    username: 'Ryan Okafor',
    lastMessage: 'Perfect, sending payment now',
    lastMessageTime: '2025-01-12T16:30:00Z',
    unreadCount: 0,
    tags: ['client', 'custom'],
    messages: [
      { id: 'm17', sender: 'user', text: 'Need to top up both accounts', timestamp: '2025-01-12T16:00:00Z' },
      { id: 'm18', sender: 'admin', text: 'Sure! Total will be $15,000. BTC address: bc1q...xyz', timestamp: '2025-01-12T16:15:00Z' },
      { id: 'm19', sender: 'user', text: 'Perfect, sending payment now', timestamp: '2025-01-12T16:30:00Z' },
    ],
  },
]

export const adminUsers: AdminUser[] = [
  { id: 'admin1', name: 'Admin', email: 'admin@adflux.store', role: 'super_admin', lastLogin: '2025-01-15T10:00:00Z', status: 'active' },
  { id: 'admin2', name: 'Support Agent', email: 'support@adflux.store', role: 'support', lastLogin: '2025-01-15T09:00:00Z', status: 'active' },
  { id: 'admin3', name: 'Viewer', email: 'viewer@adflux.store', role: 'viewer', lastLogin: '2025-01-14T14:00:00Z', status: 'active' },
  { id: 'admin4', name: 'Ops Manager', email: 'ops@adflux.store', role: 'admin', lastLogin: '2025-01-13T11:00:00Z', status: 'inactive' },
]
