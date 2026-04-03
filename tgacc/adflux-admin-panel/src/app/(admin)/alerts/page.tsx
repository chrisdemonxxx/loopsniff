"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { Bell, Plus, Loader2, AlertTriangle, Info, CheckCircle2 } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"
import { formatDateTime } from "@/lib/utils"

interface Alert {
  id: string
  title: string
  message: string
  type: string
  scope: string
  show_banner: boolean
  send_email: boolean
  active: boolean
  created_at: string
  expires_at: string | null
}

const typeVariant: Record<string, string> = {
  info: "info",
  warning: "warning",
  error: "destructive",
  success: "success",
}

const typeIcon: Record<string, React.ReactNode> = {
  info: <Info className="h-4 w-4 text-blue-400" />,
  warning: <AlertTriangle className="h-4 w-4 text-amber-400" />,
  error: <AlertTriangle className="h-4 w-4 text-red-400" />,
  success: <CheckCircle2 className="h-4 w-4 text-emerald-400" />,
}

export default function AlertsPage() {
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const token = useApiToken()
  const { data: alerts, loading, error, refetch } = useApi<Alert[]>("/admin/alerts")

  // Form state
  const [formTitle, setFormTitle] = useState("")
  const [formMessage, setFormMessage] = useState("")
  const [formType, setFormType] = useState("info")
  const [formScope, setFormScope] = useState("all")
  const [formShowBanner, setFormShowBanner] = useState(true)
  const [formSendEmail, setFormSendEmail] = useState(false)

  const resetForm = () => {
    setFormTitle("")
    setFormMessage("")
    setFormType("info")
    setFormScope("all")
    setFormShowBanner(true)
    setFormSendEmail(false)
    setFormError(null)
  }

  const handleCreateAlert = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setFormError(null)
    try {
      await apiFetch("/admin/alerts", token, {
        method: "POST",
        body: JSON.stringify({
          title: formTitle,
          message: formMessage,
          type: formType,
          scope: formScope,
          show_banner: formShowBanner,
          send_email: formSendEmail,
        }),
      })
      setAddModalOpen(false)
      resetForm()
      refetch()
    } catch (err: any) {
      setFormError(err.message || "Failed to create alert")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading alerts…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-destructive">Failed to load alerts: {error}</p>
        <Button variant="outline" onClick={refetch}>Retry</Button>
      </div>
    )
  }

  const alertList = alerts ?? []
  const activeAlerts = alertList.filter((a) => a.active)
  const expiredAlerts = alertList.filter((a) => !a.active)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bell className="h-6 w-6" /> Alerts
        </h1>
        <Button onClick={() => setAddModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" /> Create Alert
        </Button>
      </div>

      {/* Active Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Alerts ({activeAlerts.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {activeAlerts.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No active alerts</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Banner</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeAlerts.map((alert) => (
                  <TableRow key={alert.id}>
                    <TableCell>{typeIcon[alert.type] ?? typeIcon.info}</TableCell>
                    <TableCell className="font-medium">{alert.title}</TableCell>
                    <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                      {alert.message}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{alert.scope}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={alert.show_banner ? "success" : "secondary"}>
                        {alert.show_banner ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={alert.send_email ? "success" : "secondary"}>
                        {alert.send_email ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(alert.created_at)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {alert.expires_at ? formatDateTime(alert.expires_at) : "Never"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Expired Alerts */}
      {expiredAlerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-muted-foreground">
              Expired / Inactive Alerts ({expiredAlerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expired</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expiredAlerts.map((alert) => (
                  <TableRow key={alert.id} className="opacity-60">
                    <TableCell>{typeIcon[alert.type] ?? typeIcon.info}</TableCell>
                    <TableCell className="font-medium">{alert.title}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{alert.scope}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(alert.created_at)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {alert.expires_at ? formatDateTime(alert.expires_at) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create Alert Modal */}
      <Modal
        open={addModalOpen}
        onClose={() => {
          setAddModalOpen(false)
          resetForm()
        }}
        title="Create Alert"
      >
        <form className="space-y-4" onSubmit={handleCreateAlert}>
          {formError && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">
              {formError}
            </div>
          )}
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Title</label>
            <Input
              placeholder="Alert title"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Message</label>
            <Input
              placeholder="Alert message"
              value={formMessage}
              onChange={(e) => setFormMessage(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Type</label>
            <Select
              value={formType}
              onChange={(e) => setFormType(e.target.value)}
              options={[
                { value: "info", label: "Info" },
                { value: "warning", label: "Warning" },
                { value: "error", label: "Error" },
                { value: "success", label: "Success" },
              ]}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">Scope</label>
            <Select
              value={formScope}
              onChange={(e) => setFormScope(e.target.value)}
              options={[
                { value: "all", label: "All Users" },
                { value: "clients", label: "Clients Only" },
                { value: "admins", label: "Admins Only" },
              ]}
            />
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={formShowBanner}
                onChange={(e) => setFormShowBanner(e.target.checked)}
                className="rounded border-border"
              />
              Show Banner
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={formSendEmail}
                onChange={(e) => setFormSendEmail(e.target.checked)}
                className="rounded border-border"
              />
              Send Email
            </label>
          </div>
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAddModalOpen(false)
                resetForm()
              }}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Creating…
                </>
              ) : (
                "Create Alert"
              )}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
