"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Modal } from "@/components/ui/modal"
import { useToast } from "@/components/ui/toast"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table"
import { Loader2, Settings2, Plus, Pencil, Trash2 } from "lucide-react"
import { useApi, useApiToken, apiFetch } from "@/lib/api"

interface DepositConfig {
  id: string
  network: string
  currency: string
  address: string
  memo?: string | null
  label?: string | null
  active: boolean
}

const NETWORK_OPTIONS = [
  { value: "TRC20", label: "TRC20 (Tron)" },
  { value: "ERC20", label: "ERC20 (Ethereum)" },
  { value: "BEP20", label: "BEP20 (BNB Smart Chain)" },
  { value: "BTC", label: "BTC (Bitcoin)" },
  { value: "other", label: "Other" },
]

interface FormState {
  network: string
  currency: string
  address: string
  memo: string
  label: string
  active: boolean
}

const emptyForm: FormState = {
  network: "TRC20",
  currency: "USDT",
  address: "",
  memo: "",
  label: "",
  active: true,
}

export default function DepositConfigPage() {
  const token = useApiToken()
  const { toast } = useToast()
  const { data: configs, loading, error, refetch } = useApi<DepositConfig[]>("/wallet/deposit-config")

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<DepositConfig | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  const openCreate = () => {
    setEditing(null)
    setForm(emptyForm)
    setModalOpen(true)
  }

  const openEdit = (c: DepositConfig) => {
    setEditing(c)
    setForm({
      network: c.network,
      currency: c.currency,
      address: c.address,
      memo: c.memo ?? "",
      label: c.label ?? "",
      active: c.active,
    })
    setModalOpen(true)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    if (!form.address.trim() || !form.currency.trim()) {
      toast("Address and currency are required", "error")
      return
    }
    setSaving(true)
    try {
      const payload = {
        network: form.network,
        currency: form.currency.trim().toUpperCase(),
        address: form.address.trim(),
        memo: form.memo.trim() || null,
        label: form.label.trim() || null,
        active: form.active,
      }
      if (editing) {
        await apiFetch(`/admin/deposit-config/${editing.id}`, token, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
        toast("Deposit address updated", "success")
      } else {
        await apiFetch(`/admin/deposit-config`, token, {
          method: "POST",
          body: JSON.stringify(payload),
        })
        toast("Deposit address added", "success")
      }
      setModalOpen(false)
      setEditing(null)
      refetch()
    } catch (err: any) {
      toast(err?.message || "Save failed", "error")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (c: DepositConfig) => {
    if (!token) return
    if (!confirm(`Delete deposit address for ${c.network} ${c.currency}?`)) return
    setBusyId(c.id)
    try {
      await apiFetch(`/admin/deposit-config/${c.id}`, token, { method: "DELETE" })
      toast("Deposit address deleted", "success")
      refetch()
    } catch (err: any) {
      toast(err?.message || "Delete failed", "error")
    } finally {
      setBusyId(null)
    }
  }

  const toggleActive = async (c: DepositConfig) => {
    if (!token) return
    setBusyId(c.id)
    try {
      await apiFetch(`/admin/deposit-config/${c.id}`, token, {
        method: "PUT",
        body: JSON.stringify({ ...c, active: !c.active }),
      })
      toast(`Marked ${!c.active ? "active" : "inactive"}`, "success")
      refetch()
    } catch (err: any) {
      toast(err?.message || "Update failed", "error")
    } finally {
      setBusyId(null)
    }
  }

  const list = configs ?? []
  const enabledCount = list.filter((c) => c.active).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings2 className="h-6 w-6" /> Deposit Configuration
        </h1>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Add Address
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Total Addresses</span>
            <span className="text-xl font-bold">{list.length}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Active</span>
            <span className="text-xl font-bold text-emerald-400">{enabledCount}</span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <span className="text-xs text-muted-foreground block">Inactive</span>
            <span className="text-xl font-bold text-red-400">{list.length - enabledCount}</span>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Deposit Addresses</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground text-sm">Loading…</span>
            </div>
          ) : error ? (
            <div className="text-center py-8 space-y-3">
              <p className="text-destructive text-sm">Failed to load: {error}</p>
              <Button variant="outline" size="sm" onClick={refetch}>Retry</Button>
            </div>
          ) : list.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">
              No deposit addresses configured. Click “Add Address” to create one.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Network</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead>Address</TableHead>
                  <TableHead>Memo</TableHead>
                  <TableHead>Label</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.network}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{c.currency}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[220px] truncate" title={c.address}>
                      {c.address}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{c.memo || "—"}</TableCell>
                    <TableCell className="text-xs">{c.label || "—"}</TableCell>
                    <TableCell>
                      <button
                        type="button"
                        disabled={busyId === c.id}
                        onClick={() => toggleActive(c)}
                        className="disabled:opacity-50"
                      >
                        <Badge variant={c.active ? "success" : "destructive"}>
                          {c.active ? "Active" : "Inactive"}
                        </Badge>
                      </button>
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(c)}
                        disabled={busyId === c.id}
                        title="Edit"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => remove(c)}
                        disabled={busyId === c.id}
                        title="Delete"
                      >
                        {busyId === c.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4 text-red-400" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => !saving && setModalOpen(false)}
        title={editing ? "Edit Deposit Address" : "Add Deposit Address"}
      >
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs text-muted-foreground block mb-1.5">Network</label>
            <Select
              value={form.network}
              onChange={(e) => setForm({ ...form, network: e.target.value })}
              options={NETWORK_OPTIONS}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1.5">Currency</label>
            <Input
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
              placeholder="USDT"
              required
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1.5">Address</label>
            <Input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="Wallet address"
              required
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1.5">Memo / Tag (optional)</label>
            <Input
              value={form.memo}
              onChange={(e) => setForm({ ...form, memo: e.target.value })}
              placeholder="Optional destination tag"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1.5">Label</label>
            <Input
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="Internal label"
            />
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(e) => setForm({ ...form, active: e.target.checked })}
              className="rounded border-border"
            />
            Active
          </label>
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {editing ? "Save changes" : "Add address"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
