export interface AdAccount {
  id: string;
  name: string;
  platform: "Google" | "Meta" | "TikTok";
  status: "active" | "banned" | "paused";
  balance: number;
  dailySpend: number;
  totalSpend: number;
  createdAt: string;
  campaigns: Campaign[];
  statusHistory: StatusEvent[];
}

export interface Campaign {
  id: string;
  name: string;
  status: "active" | "paused" | "ended";
  budget: number;
  spent: number;
  impressions: number;
  clicks: number;
  conversions: number;
}

export interface StatusEvent {
  date: string;
  status: string;
  note: string;
}

export interface Transaction {
  id: string;
  date: string;
  type: "topup" | "spend" | "refund" | "ban_transfer";
  amount: number;
  commission: number;
  crypto: string;
  status: "completed" | "pending" | "failed";
  accountName?: string;
  description: string;
}

export interface DailySpend {
  date: string;
  amount: number;
  google: number;
  meta: number;
  tiktok: number;
}

export interface ChatMessage {
  id: string;
  sender: "client" | "ai" | "admin";
  text: string;
  timestamp: string;
}

export interface ChatSession {
  id: string;
  subject: string;
  status: "open" | "resolved";
  agentType: "ai" | "human";
  lastMessage: string;
  lastMessageTime: string;
  messages: ChatMessage[];
}

export interface ClientUser {
  id: string;
  name: string;
  email: string;
  telegram: string;
  tier: "starter" | "growth" | "scale" | "enterprise";
  commissionRate: number;
  totalBalance: number;
  monthlySpend: number;
}

export const mockUser: ClientUser = {
  id: "usr_001",
  name: "Alex Thompson",
  email: "demo@adflux.store",
  telegram: "@alexthompson",
  tier: "growth",
  commissionRate: 5,
  totalBalance: 24750.0,
  monthlySpend: 18420.5,
};

export const mockAccounts: AdAccount[] = [
  {
    id: "acc_001",
    name: "AT Google Ads - Main",
    platform: "Google",
    status: "active",
    balance: 12500.0,
    dailySpend: 850.0,
    totalSpend: 45230.0,
    createdAt: "2024-08-15",
    campaigns: [
      { id: "cmp_001", name: "Brand Search US", status: "active", budget: 500, spent: 423.5, impressions: 125000, clicks: 8750, conversions: 350 },
      { id: "cmp_002", name: "Shopping - Electronics", status: "active", budget: 300, spent: 287.0, impressions: 89000, clicks: 4200, conversions: 210 },
      { id: "cmp_003", name: "Display Remarketing", status: "paused", budget: 200, spent: 0, impressions: 0, clicks: 0, conversions: 0 },
    ],
    statusHistory: [
      { date: "2024-08-15", status: "Created", note: "Account provisioned" },
      { date: "2024-08-16", status: "Active", note: "First campaign launched" },
      { date: "2024-11-01", status: "Review", note: "Policy review triggered" },
      { date: "2024-11-03", status: "Active", note: "Review passed" },
    ],
  },
  {
    id: "acc_002",
    name: "AT Meta Ads - Ecom",
    platform: "Meta",
    status: "active",
    balance: 8250.0,
    dailySpend: 620.0,
    totalSpend: 32100.0,
    createdAt: "2024-09-01",
    campaigns: [
      { id: "cmp_004", name: "Conversion - Lookalike", status: "active", budget: 400, spent: 378.0, impressions: 210000, clicks: 6300, conversions: 280 },
      { id: "cmp_005", name: "Retargeting - ATC", status: "active", budget: 250, spent: 242.0, impressions: 156000, clicks: 4680, conversions: 195 },
    ],
    statusHistory: [
      { date: "2024-09-01", status: "Created", note: "Account provisioned" },
      { date: "2024-09-02", status: "Active", note: "BM verified" },
    ],
  },
  {
    id: "acc_003",
    name: "AT TikTok Ads - Test",
    platform: "TikTok",
    status: "banned",
    balance: 0,
    dailySpend: 0,
    totalSpend: 8900.0,
    createdAt: "2024-10-10",
    campaigns: [
      { id: "cmp_006", name: "Spark Ads - UGC", status: "ended", budget: 300, spent: 300, impressions: 450000, clicks: 13500, conversions: 540 },
    ],
    statusHistory: [
      { date: "2024-10-10", status: "Created", note: "Account provisioned" },
      { date: "2024-10-11", status: "Active", note: "First ad approved" },
      { date: "2024-12-05", status: "Under Review", note: "Policy violation flagged" },
      { date: "2024-12-07", status: "Banned", note: "Account permanently suspended - funds transferred" },
    ],
  },
];

export const mockTransactions: Transaction[] = [
  { id: "txn_001", date: "2025-01-15T10:30:00", type: "topup", amount: 5000, commission: 250, crypto: "USDT", status: "completed", description: "Crypto top-up via USDT" },
  { id: "txn_002", date: "2025-01-14T08:00:00", type: "spend", amount: -850, commission: 0, crypto: "", status: "completed", accountName: "AT Google Ads - Main", description: "Daily ad spend" },
  { id: "txn_003", date: "2025-01-14T08:00:00", type: "spend", amount: -620, commission: 0, crypto: "", status: "completed", accountName: "AT Meta Ads - Ecom", description: "Daily ad spend" },
  { id: "txn_004", date: "2025-01-13T14:20:00", type: "topup", amount: 3000, commission: 150, crypto: "ETH", status: "completed", description: "Crypto top-up via ETH" },
  { id: "txn_005", date: "2025-01-12T09:00:00", type: "spend", amount: -780, commission: 0, crypto: "", status: "completed", accountName: "AT Google Ads - Main", description: "Daily ad spend" },
  { id: "txn_006", date: "2025-01-11T16:45:00", type: "refund", amount: 2400, commission: 0, crypto: "USDT", status: "completed", description: "Ban refund - TikTok account" },
  { id: "txn_007", date: "2025-01-11T16:45:00", type: "ban_transfer", amount: 2400, commission: 0, crypto: "", status: "completed", accountName: "AT TikTok Ads - Test", description: "Banned account fund transfer" },
  { id: "txn_008", date: "2025-01-10T11:00:00", type: "topup", amount: 10000, commission: 500, crypto: "BTC", status: "completed", description: "Crypto top-up via BTC" },
  { id: "txn_009", date: "2025-01-09T08:00:00", type: "spend", amount: -920, commission: 0, crypto: "", status: "completed", accountName: "AT Google Ads - Main", description: "Daily ad spend" },
  { id: "txn_010", date: "2025-01-08T08:00:00", type: "spend", amount: -540, commission: 0, crypto: "", status: "completed", accountName: "AT Meta Ads - Ecom", description: "Daily ad spend" },
  { id: "txn_011", date: "2025-01-07T13:00:00", type: "topup", amount: 2000, commission: 100, crypto: "USDC", status: "pending", description: "Crypto top-up via USDC - awaiting confirmation" },
  { id: "txn_012", date: "2025-01-06T08:00:00", type: "spend", amount: -710, commission: 0, crypto: "", status: "completed", accountName: "AT Google Ads - Main", description: "Daily ad spend" },
  { id: "txn_013", date: "2025-01-05T08:00:00", type: "spend", amount: -680, commission: 0, crypto: "", status: "completed", accountName: "AT Meta Ads - Ecom", description: "Daily ad spend" },
  { id: "txn_014", date: "2025-01-04T19:30:00", type: "topup", amount: 7500, commission: 375, crypto: "USDT", status: "completed", description: "Crypto top-up via USDT" },
  { id: "txn_015", date: "2025-01-03T08:00:00", type: "spend", amount: -830, commission: 0, crypto: "", status: "completed", accountName: "AT Google Ads - Main", description: "Daily ad spend" },
];

function generateDailySpend(): DailySpend[] {
  const data: DailySpend[] = [];
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const google = 600 + Math.random() * 500;
    const meta = 400 + Math.random() * 400;
    const tiktok = i > 20 ? 200 + Math.random() * 200 : 0;
    data.push({
      date: date.toISOString().split("T")[0],
      amount: Math.round((google + meta + tiktok) * 100) / 100,
      google: Math.round(google * 100) / 100,
      meta: Math.round(meta * 100) / 100,
      tiktok: Math.round(tiktok * 100) / 100,
    });
  }
  return data;
}

export const mockDailySpend: DailySpend[] = generateDailySpend();

export const mockChatSessions: ChatSession[] = [
  {
    id: "chat_001",
    subject: "Account top-up issue",
    status: "open",
    agentType: "ai",
    lastMessage: "I can help you with that! Could you share the transaction ID?",
    lastMessageTime: "2025-01-15T10:35:00",
    messages: [
      { id: "msg_001", sender: "client", text: "Hi, my top-up hasn't been credited yet. It's been 2 hours.", timestamp: "2025-01-15T10:30:00" },
      { id: "msg_002", sender: "ai", text: "Hello Alex! I'm sorry to hear about the delay. Let me look into this for you.", timestamp: "2025-01-15T10:31:00" },
      { id: "msg_003", sender: "ai", text: "I can help you with that! Could you share the transaction ID?", timestamp: "2025-01-15T10:31:30" },
      { id: "msg_004", sender: "client", text: "Sure, it's txn_011", timestamp: "2025-01-15T10:33:00" },
      { id: "msg_005", sender: "ai", text: "Thank you! I can see transaction txn_011 for $2,000 USDC. It's currently showing as 'pending' — the blockchain confirmation is still processing. This typically takes 15-30 minutes for USDC. I'll monitor it and notify you once it's confirmed.", timestamp: "2025-01-15T10:35:00" },
    ],
  },
  {
    id: "chat_002",
    subject: "TikTok account ban appeal",
    status: "resolved",
    agentType: "human",
    lastMessage: "The funds from your banned TikTok account have been transferred. You should see the $2,400 credit now.",
    lastMessageTime: "2025-01-11T17:00:00",
    messages: [
      { id: "msg_006", sender: "client", text: "My TikTok ad account just got banned. What are my options?", timestamp: "2025-01-11T15:00:00" },
      { id: "msg_007", sender: "ai", text: "I'm sorry to hear about the ban. Let me connect you with a human agent who can review your account and discuss options.", timestamp: "2025-01-11T15:01:00" },
      { id: "msg_008", sender: "admin", text: "Hi Alex, I'm Sarah from the AdFlux support team. I can see your TikTok account AT TikTok Ads - Test was flagged for a policy violation. Let me review the details.", timestamp: "2025-01-11T15:30:00" },
      { id: "msg_009", sender: "client", text: "Thanks Sarah. Is there any chance of getting it reinstated?", timestamp: "2025-01-11T15:35:00" },
      { id: "msg_010", sender: "admin", text: "Unfortunately, TikTok has marked this as a permanent suspension. However, I've initiated a fund transfer for the remaining balance of $2,400 to your main AdFlux wallet.", timestamp: "2025-01-11T16:30:00" },
      { id: "msg_011", sender: "admin", text: "The funds from your banned TikTok account have been transferred. You should see the $2,400 credit now.", timestamp: "2025-01-11T17:00:00" },
    ],
  },
];
