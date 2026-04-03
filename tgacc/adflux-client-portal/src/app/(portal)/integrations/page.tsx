"use client";

import React, { useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useApi, useApiToken, apiFetch, API_URL } from "@/lib/api";
import {
  Globe,
  Image,
  Link2,
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
  Trash2,
  Plus,
  Shield,
  Megaphone,
} from "lucide-react";

interface FacebookPage {
  id: string;
  name: string;
  category?: string;
  connected: boolean;
}

interface InstagramAccount {
  id: string;
  username?: string;
  name?: string;
  profile_picture_url?: string;
  followers_count?: number;
  connected: boolean;
}

interface MetaAdAccount {
  id: string;
  account_id: string;
  name: string;
  currency?: string;
  timezone?: string;
  business_name?: string;
  connected: boolean;
}

interface ConnectionStatus {
  connected: boolean;
  facebook_user_id?: string;
  facebook_user_name?: string;
  connected_at?: string;
  pages: FacebookPage[];
  instagram_accounts: InstagramAccount[];
  ad_accounts: MetaAdAccount[];
}

export default function IntegrationsPage() {
  const { data: session } = useSession();
  const token = useApiToken();
  const {
    data: status,
    loading,
    error,
    refetch,
  } = useApi<ConnectionStatus>("/facebook/status");

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showPages, setShowPages] = useState(false);
  const [showIgAccounts, setShowIgAccounts] = useState(false);
  const [showAdAccounts, setShowAdAccounts] = useState(false);
  const [availablePages, setAvailablePages] = useState<FacebookPage[]>([]);
  const [availableIg, setAvailableIg] = useState<InstagramAccount[]>([]);
  const [availableAdAccounts, setAvailableAdAccounts] = useState<MetaAdAccount[]>([]);

  const handleConnect = useCallback(async () => {
    if (!token) return;
    setActionLoading("connect");
    try {
      const data = await apiFetch<{ auth_url: string }>(
        "/facebook/auth-url",
        token
      );
      window.location.href = data.auth_url;
    } catch {
      alert("Failed to start Facebook connection");
    } finally {
      setActionLoading(null);
    }
  }, [token]);

  const handleDisconnect = useCallback(async () => {
    if (!token || !confirm("Disconnect Facebook? This will remove all connected pages and accounts.")) return;
    setActionLoading("disconnect");
    try {
      await apiFetch("/facebook/disconnect", token, { method: "DELETE" });
      refetch();
    } catch {
      alert("Failed to disconnect");
    } finally {
      setActionLoading(null);
    }
  }, [token, refetch]);

  const fetchPages = useCallback(async () => {
    if (!token) return;
    setActionLoading("pages");
    try {
      const data = await apiFetch<{ pages: FacebookPage[] }>(
        "/facebook/pages",
        token
      );
      setAvailablePages(data.pages);
      setShowPages(true);
    } catch {
      alert("Failed to fetch pages");
    } finally {
      setActionLoading(null);
    }
  }, [token]);

  const connectPage = useCallback(
    async (pageId: string) => {
      if (!token) return;
      setActionLoading(`page-${pageId}`);
      try {
        await apiFetch(`/facebook/pages/${pageId}/connect`, token, {
          method: "POST",
        });
        refetch();
        setShowPages(false);
      } catch {
        alert("Failed to connect page");
      } finally {
        setActionLoading(null);
      }
    },
    [token, refetch]
  );

  const fetchIgAccounts = useCallback(async () => {
    if (!token) return;
    setActionLoading("ig");
    try {
      const data = await apiFetch<{ accounts: InstagramAccount[] }>(
        "/facebook/instagram-accounts",
        token
      );
      setAvailableIg(data.accounts);
      setShowIgAccounts(true);
    } catch {
      alert("Failed to fetch Instagram accounts");
    } finally {
      setActionLoading(null);
    }
  }, [token]);

  const connectIg = useCallback(
    async (igId: string) => {
      if (!token) return;
      setActionLoading(`ig-${igId}`);
      try {
        await apiFetch(`/facebook/instagram-accounts/${igId}/connect`, token, {
          method: "POST",
        });
        refetch();
        setShowIgAccounts(false);
      } catch {
        alert("Failed to connect Instagram account");
      } finally {
        setActionLoading(null);
      }
    },
    [token, refetch]
  );

  const fetchAdAccounts = useCallback(async () => {
    if (!token) return;
    setActionLoading("ad-accounts");
    try {
      const data = await apiFetch<{ ad_accounts: MetaAdAccount[] }>(
        "/facebook/ad-accounts",
        token
      );
      setAvailableAdAccounts(data.ad_accounts);
      setShowAdAccounts(true);
    } catch {
      alert("Failed to fetch ad accounts");
    } finally {
      setActionLoading(null);
    }
  }, [token]);

  const connectAdAccount = useCallback(
    async (adAccountId: string) => {
      if (!token) return;
      setActionLoading(`ad-${adAccountId}`);
      try {
        await apiFetch(
          `/facebook/ad-accounts/${adAccountId}/connect`,
          token,
          { method: "POST" }
        );
        refetch();
        setShowAdAccounts(false);
      } catch {
        alert("Failed to connect ad account");
      } finally {
        setActionLoading(null);
      }
    },
    [token, refetch]
  );

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
      </div>
    );
  }

  const connected = status?.connected ?? false;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Integrations</h1>
        <p className="text-sm text-gray-400">
          Connect your Facebook, Instagram, and Meta ad accounts
        </p>
      </div>

      {/* Facebook Connection Card */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-600/20">
              <Globe className="h-6 w-6 text-blue-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">
                Facebook & Instagram
              </h2>
              <p className="text-sm text-gray-400">
                {connected
                  ? `Connected as ${status?.facebook_user_name || "Unknown"}`
                  : "Connect to manage pages, Instagram, and ad accounts"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {connected ? (
              <>
                <span className="flex items-center gap-1.5 rounded-full bg-green-900/30 px-3 py-1 text-xs font-medium text-green-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Connected
                </span>
                <button
                  onClick={handleDisconnect}
                  disabled={actionLoading === "disconnect"}
                  className="flex items-center gap-1.5 rounded-lg border border-red-800 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-900/20 disabled:opacity-50"
                >
                  {actionLoading === "disconnect" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  Disconnect
                </button>
              </>
            ) : (
              <>
                <span className="flex items-center gap-1.5 rounded-full bg-gray-800 px-3 py-1 text-xs font-medium text-gray-400">
                  <XCircle className="h-3.5 w-3.5" />
                  Not Connected
                </span>
                <button
                  onClick={handleConnect}
                  disabled={actionLoading === "connect"}
                  className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
                >
                  {actionLoading === "connect" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <ExternalLink className="h-3.5 w-3.5" />
                  )}
                  Connect with Facebook
                </button>
              </>
            )}
          </div>
        </div>

        {/* Permissions info */}
        {!connected && (
          <div className="mt-4 rounded-lg border border-gray-800 bg-gray-950 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
              <Shield className="h-4 w-4 text-blue-400" />
              Permissions we&apos;ll request
            </div>
            <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs text-gray-500 sm:grid-cols-4">
              <span>• Ads Management</span>
              <span>• Pages List</span>
              <span>• Instagram Basic</span>
              <span>• Business Management</span>
              <span>• Read Insights</span>
              <span>• Instagram Insights</span>
              <span>• Page Engagement</span>
              <span>• Ads Read</span>
            </div>
          </div>
        )}
      </div>

      {/* Connected Resources */}
      {connected && (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Connected Pages */}
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Globe className="h-4 w-4 text-blue-400" />
                Pages
              </h3>
              <button
                onClick={fetchPages}
                disabled={actionLoading === "pages"}
                className="flex items-center gap-1 rounded-md bg-gray-800 px-2.5 py-1 text-xs text-gray-300 transition hover:bg-gray-700 disabled:opacity-50"
              >
                {actionLoading === "pages" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Plus className="h-3 w-3" />
                )}
                Add
              </button>
            </div>
            {status?.pages && status.pages.length > 0 ? (
              <div className="space-y-2">
                {status.pages.map((page) => (
                  <div
                    key={page.id}
                    className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-3 py-2"
                  >
                    <span className="text-sm text-gray-300">{page.name}</span>
                    <CheckCircle2 className="h-4 w-4 text-green-400" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No pages connected</p>
            )}
          </div>

          {/* Connected Instagram Accounts */}
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Image className="h-4 w-4 text-pink-400" />
                Instagram
              </h3>
              <button
                onClick={fetchIgAccounts}
                disabled={actionLoading === "ig"}
                className="flex items-center gap-1 rounded-md bg-gray-800 px-2.5 py-1 text-xs text-gray-300 transition hover:bg-gray-700 disabled:opacity-50"
              >
                {actionLoading === "ig" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Plus className="h-3 w-3" />
                )}
                Add
              </button>
            </div>
            {status?.instagram_accounts &&
            status.instagram_accounts.length > 0 ? (
              <div className="space-y-2">
                {status.instagram_accounts.map((ig) => (
                  <div
                    key={ig.id}
                    className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-3 py-2"
                  >
                    <span className="text-sm text-gray-300">
                      @{ig.username || ig.name || ig.id}
                    </span>
                    <CheckCircle2 className="h-4 w-4 text-green-400" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No Instagram accounts connected</p>
            )}
          </div>

          {/* Connected Ad Accounts */}
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Megaphone className="h-4 w-4 text-violet-400" />
                Ad Accounts
              </h3>
              <button
                onClick={fetchAdAccounts}
                disabled={actionLoading === "ad-accounts"}
                className="flex items-center gap-1 rounded-md bg-gray-800 px-2.5 py-1 text-xs text-gray-300 transition hover:bg-gray-700 disabled:opacity-50"
              >
                {actionLoading === "ad-accounts" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Plus className="h-3 w-3" />
                )}
                Add
              </button>
            </div>
            {status?.ad_accounts && status.ad_accounts.length > 0 ? (
              <div className="space-y-2">
                {status.ad_accounts.map((acct) => (
                  <div
                    key={acct.id}
                    className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-3 py-2"
                  >
                    <div>
                      <span className="text-sm text-gray-300">
                        {acct.name}
                      </span>
                      <span className="ml-2 text-xs text-gray-500">
                        {acct.account_id}
                      </span>
                    </div>
                    <CheckCircle2 className="h-4 w-4 text-green-400" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No ad accounts connected</p>
            )}
          </div>
        </div>
      )}

      {/* Add Pages Modal/Drawer */}
      {showPages && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Available Pages
            </h3>
            <button
              onClick={() => setShowPages(false)}
              className="text-xs text-gray-400 hover:text-white"
            >
              Close
            </button>
          </div>
          {availablePages.length === 0 ? (
            <p className="text-xs text-gray-500">
              No pages found on your Facebook account
            </p>
          ) : (
            <div className="space-y-2">
              {availablePages.map((page) => (
                <div
                  key={page.id}
                  className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-200">
                      {page.name}
                    </p>
                    {page.category && (
                      <p className="text-xs text-gray-500">{page.category}</p>
                    )}
                  </div>
                  {page.connected ? (
                    <span className="text-xs text-green-400">Connected</span>
                  ) : (
                    <button
                      onClick={() => connectPage(page.id)}
                      disabled={actionLoading === `page-${page.id}`}
                      className="rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {actionLoading === `page-${page.id}` ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        "Connect"
                      )}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add Instagram Modal/Drawer */}
      {showIgAccounts && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Available Instagram Accounts
            </h3>
            <button
              onClick={() => setShowIgAccounts(false)}
              className="text-xs text-gray-400 hover:text-white"
            >
              Close
            </button>
          </div>
          {availableIg.length === 0 ? (
            <p className="text-xs text-gray-500">
              No Instagram business accounts found. Make sure your pages have
              linked Instagram accounts.
            </p>
          ) : (
            <div className="space-y-2">
              {availableIg.map((ig) => (
                <div
                  key={ig.id}
                  className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-200">
                      @{ig.username || ig.id}
                    </p>
                    {ig.followers_count !== undefined && (
                      <p className="text-xs text-gray-500">
                        {ig.followers_count.toLocaleString()} followers
                      </p>
                    )}
                  </div>
                  {ig.connected ? (
                    <span className="text-xs text-green-400">Connected</span>
                  ) : (
                    <button
                      onClick={() => connectIg(ig.id)}
                      disabled={actionLoading === `ig-${ig.id}`}
                      className="rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {actionLoading === `ig-${ig.id}` ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        "Connect"
                      )}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add Ad Accounts Modal/Drawer */}
      {showAdAccounts && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Available Ad Accounts
            </h3>
            <button
              onClick={() => setShowAdAccounts(false)}
              className="text-xs text-gray-400 hover:text-white"
            >
              Close
            </button>
          </div>
          {availableAdAccounts.length === 0 ? (
            <p className="text-xs text-gray-500">
              No ad accounts found in your Meta Business Manager
            </p>
          ) : (
            <div className="space-y-2">
              {availableAdAccounts.map((acct) => (
                <div
                  key={acct.id}
                  className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-200">
                      {acct.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {acct.account_id}
                      {acct.currency && ` · ${acct.currency}`}
                      {acct.business_name && ` · ${acct.business_name}`}
                    </p>
                  </div>
                  {acct.connected ? (
                    <span className="text-xs text-green-400">Connected</span>
                  ) : (
                    <button
                      onClick={() => connectAdAccount(acct.id)}
                      disabled={actionLoading === `ad-${acct.id}`}
                      className="rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {actionLoading === `ad-${acct.id}` ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        "Connect"
                      )}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
