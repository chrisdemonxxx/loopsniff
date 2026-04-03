"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { UserPlus, Key, Bell, Shield, Loader2, AlertCircle, Users, Eye, EyeOff } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { useToast } from "@/components/ui/toast"
import { formatDateTime } from "@/lib/utils"

type AdminRole = "super_admin" | "admin" | "support" | "viewer"

interface AdminUser {
  id: string
  email: string
  name: string
  role: AdminRole
  is_active: boolean
  created_at: string
}

const roleVariant: Record<AdminRole, string> = {
  super_admin: "default",
  admin: "info",
  support: "warning",
  viewer: "secondary",
}

const roleOptions = [
  { value: "super_admin", label: "Super Admin" },
  { value: "admin", label: "Admin" },
  { value: "support", label: "Support" },
  { value: "viewer", label: "Viewer" },
]

export default function SettingsPage() {
  const { data: users, loading, error, refetch } = useApi<AdminUser[]>("/admin/users")
  const token = useApiToken()

  const [editingUser, setEditingUser] = useState<AdminUser | null>(null)
  const [editName, setEditName] = useState("")
  const [editRole, setEditRole] = useState<AdminRole>("viewer")
  const [editActive, setEditActive] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Invite Admin
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState<AdminRole>("viewer")
  const [inviting, setInviting] = useState(false)

  // Notification preferences
  const [notifications, setNotifications] = useState({
    accountBanned: true,
    newClient: true,
    paymentReceived: true,
    escalation: true,
    leadStageChange: false,
    dailySummary: false,
  })

  // API Keys reveal
  const [revealedKeys, setRevealedKeys] = useState<Record<string, string | null>>({})
  const [revealingKey, setRevealingKey] = useState<string | null>(null)

  // System Config
  const [commissionRate, setCommissionRate] = useState("8")
  const [dailyLimit, setDailyLimit] = useState("5000")
  const [autoReplace, setAutoReplace] = useState("enabled")
  const [defaultCurrency, setDefaultCurrency] = useState("USD")
  const [savingConfig, setSavingConfig] = useState(false)

  const { toast } = useToast()

  const notificationPrefs = [
    { key: "accountBanned" as const, label: "Account banned alerts" },
    { key: "newClient" as const, label: "New client onboarded" },
    { key: "paymentReceived" as const, label: "Payment received" },
    { key: "escalation" as const, label: "Escalation created" },
    { key: "leadStageChange" as const, label: "Lead stage changes" },
    { key: "dailySummary" as const, label: "Daily summary email" },
  ]

  const apiKeys = [
    { id: "production", label: "Production API Key", masked: "sk-prod-••••••••••••••••••••3f8a" },
    { id: "bot-token", label: "Bot Token", masked: "bot-••••••••••••••••••••9c2d" },
    { id: "webhook-secret", label: "Webhook Secret", masked: "whsec-••••••••••••••••7b4e" },
  ]

  const handleInvite = async () => {
    if (!inviteEmail.trim() || !token) return
    setInviting(true)
    try {
      await apiFetch("/admin/invite", token, {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      })
      toast("Invitation sent successfully", "success")
      setInviteOpen(false)
      setInviteEmail("")
      setInviteRole("viewer")
      refetch()
    } catch (e: any) {
      toast(e.message || "Failed to send invitation", "error")
    } finally {
      setInviting(false)
    }
  }

  const handleRevealKey = async (keyId: string) => {
    if (revealedKeys[keyId]) {
      setRevealedKeys(prev => {
        const next = { ...prev }
        delete next[keyId]
        return next
      })
      return
    }
    setRevealingKey(keyId)
    try {
      const data = await apiFetch<{ value: string }>(`/admin/api-keys/${keyId}`, token)
      setRevealedKeys(prev => ({ ...prev, [keyId]: data.value }))
    } catch (e: any) {
      toast(e.message || "Failed to reveal key", "error")
    } finally {
      setRevealingKey(null)
    }
  }

  const handleSaveConfig = async () => {
    if (!token) return
    setSavingConfig(true)
    try {
      await apiFetch("/settings", token, {
        method: "PUT",
        body: JSON.stringify({
          commission_rate: parseFloat(commissionRate),
          daily_spend_limit: parseFloat(dailyLimit),
          auto_replace_banned: autoReplace,
          default_currency: defaultCurrency,
          notifications,
        }),
      })
      toast("Configuration saved", "success")
    } catch (e: any) {
      toast(e.message || "Failed to save configuration", "error")
    } finally {
      setSavingConfig(false)
    }
  }

  const toggleNotification = (key: keyof typeof notifications) => {
    setNotifications(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const openEdit = (user: AdminUser) => {
    setEditingUser(user)
    setEditName(user.name)
    setEditRole(user.role)
    setEditActive(user.is_active)
    setSaveError(null)
  }

  const handleSave = async () => {
    if (!editingUser || !token) return
    setSaving(true)
    setSaveError(null)
    try {
      await apiFetch(`/admin/users/${editingUser.id}`, token, {
        method: "PUT",
        body: JSON.stringify({ name: editName, role: editRole, is_active: editActive }),
      })
      setEditingUser(null)
      refetch()
    } catch (e: any) {
      setSaveError(e.message || "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  const usersContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )
    }
    if (error) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-2">
          <AlertCircle className="h-6 w-6" />
          <p className="text-sm">Failed to load admin users: {error}</p>
        </div>
      )
    }
    if (!users?.length) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-2">
          <Users className="h-6 w-6" />
          <p className="text-sm">No admin users found</p>
        </div>
      )
    }
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Status</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((admin) => (
            <TableRow key={admin.id}>
              <TableCell className="font-medium">{admin.name}</TableCell>
              <TableCell className="text-muted-foreground">{admin.email}</TableCell>
              <TableCell>
                <Badge variant={roleVariant[admin.role] as any}>{admin.role}</Badge>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatDateTime(admin.created_at)}
              </TableCell>
              <TableCell>
                <Badge variant={admin.is_active ? "success" : "secondary"}>
                  {admin.is_active ? "active" : "inactive"}
                </Badge>
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => openEdit(admin)}>
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Edit User Modal */}
      <Modal open={!!editingUser} onClose={() => setEditingUser(null)} title="Edit Admin User">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Name</label>
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Role</label>
            <Select
              options={roleOptions}
              value={editRole}
              onChange={(e) => setEditRole(e.target.value as AdminRole)}
            />
          </div>
          <div className="flex items-center justify-between p-2 rounded-md hover:bg-secondary/50">
            <span className="text-sm">Active</span>
            <button
              type="button"
              onClick={() => setEditActive(!editActive)}
              className={`w-10 h-5 rounded-full transition-colors ${editActive ? "bg-emerald-500" : "bg-secondary"}`}
            >
              <div
                className={`h-4 w-4 rounded-full bg-white transition-transform ${editActive ? "translate-x-5" : "translate-x-0.5"}`}
              />
            </button>
          </div>
          {saveError && <p className="text-sm text-red-500">{saveError}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditingUser(null)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
              Save
            </Button>
          </div>
        </div>
      </Modal>

      {/* Invite Admin Modal */}
      <Modal open={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite Admin">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Email</label>
            <Input type="email" placeholder="admin@example.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Role</label>
            <Select options={roleOptions} value={inviteRole} onChange={(e) => setInviteRole(e.target.value as AdminRole)} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setInviteOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleInvite} disabled={inviting || !inviteEmail.trim()}>
              {inviting && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
              Send Invitation
            </Button>
          </div>
        </div>
      </Modal>

      {/* Admin Users */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="h-4 w-4" /> Admin Users
            </CardTitle>
            <Button size="sm" onClick={() => setInviteOpen(true)}>
              <UserPlus className="h-3 w-3 mr-2" /> Invite Admin
            </Button>
          </div>
        </CardHeader>
        <CardContent>{usersContent()}</CardContent>
      </Card>

      {/* Roles Description */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Role Permissions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 rounded-md border border-border">
              <Badge variant="default" className="mb-2">super_admin</Badge>
              <p className="text-xs text-muted-foreground">Full access to all features, user management, system configuration</p>
            </div>
            <div className="p-3 rounded-md border border-border">
              <Badge variant="info" className="mb-2">admin</Badge>
              <p className="text-xs text-muted-foreground">Manage clients, accounts, finances. Cannot manage admin users</p>
            </div>
            <div className="p-3 rounded-md border border-border">
              <Badge variant="warning" className="mb-2">support</Badge>
              <p className="text-xs text-muted-foreground">View clients, respond to bot messages, handle escalations</p>
            </div>
            <div className="p-3 rounded-md border border-border">
              <Badge variant="secondary" className="mb-2">viewer</Badge>
              <p className="text-xs text-muted-foreground">Read-only access to all dashboards and data</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Bell className="h-4 w-4" /> Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {notificationPrefs.map((pref) => (
              <div key={pref.key} className="flex items-center justify-between p-2 rounded-md hover:bg-secondary/50">
                <span className="text-sm">{pref.label}</span>
                <button
                  type="button"
                  onClick={() => toggleNotification(pref.key)}
                  className={`w-10 h-5 rounded-full transition-colors ${notifications[pref.key] ? 'bg-emerald-500' : 'bg-secondary'}`}
                >
                  <div className={`h-4 w-4 rounded-full bg-white transition-transform ${notifications[pref.key] ? 'translate-x-5' : 'translate-x-0.5'}`} />
                </button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Key className="h-4 w-4" /> API Keys
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {apiKeys.map((key) => (
              <div key={key.id} className="flex items-center justify-between p-3 rounded-md border border-border">
                <div>
                  <span className="text-sm font-medium block">{key.label}</span>
                  <span className="text-xs text-muted-foreground font-mono">
                    {revealedKeys[key.id] ?? key.masked}
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleRevealKey(key.id)}
                  disabled={revealingKey === key.id}
                >
                  {revealingKey === key.id ? (
                    <Loader2 className="h-3 w-3 mr-2 animate-spin" />
                  ) : revealedKeys[key.id] ? (
                    <EyeOff className="h-3 w-3 mr-2" />
                  ) : (
                    <Eye className="h-3 w-3 mr-2" />
                  )}
                  {revealedKeys[key.id] ? "Hide" : "Reveal"}
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* System Config */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">System Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Default Commission Rate (%)</label>
              <Input type="number" value={commissionRate} onChange={(e) => setCommissionRate(e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Max Daily Spend Limit</label>
              <Input type="number" value={dailyLimit} onChange={(e) => setDailyLimit(e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Auto-replace Banned Accounts</label>
              <Select options={[
                { value: "enabled", label: "Enabled" },
                { value: "disabled", label: "Disabled" },
              ]} value={autoReplace} onChange={(e) => setAutoReplace(e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Default Currency</label>
              <Select options={[
                { value: "USD", label: "USD" },
                { value: "BTC", label: "BTC" },
                { value: "ETH", label: "ETH" },
                { value: "USDT", label: "USDT" },
              ]} value={defaultCurrency} onChange={(e) => setDefaultCurrency(e.target.value)} />
            </div>
          </div>
          <Button className="mt-4" size="sm" onClick={handleSaveConfig} disabled={savingConfig}>
            {savingConfig && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
            Save Configuration
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
