"use client"

import * as React from "react"
import { Modal } from "@/components/ui/modal"
import { Button } from "@/components/ui/button"

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  onConfirm: () => void | Promise<void>
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title = "Are you sure?",
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  onConfirm,
}: ConfirmDialogProps) {
  const [busy, setBusy] = React.useState(false)

  const handleConfirm = async () => {
    try {
      setBusy(true)
      await onConfirm()
      onOpenChange(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={() => !busy && onOpenChange(false)} title={title}>
      {description && (
        <p className="mb-4 text-sm text-muted-foreground">{description}</p>
      )}
      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => onOpenChange(false)}
          disabled={busy}
        >
          {cancelLabel}
        </Button>
        <Button
          variant={destructive ? "destructive" : "default"}
          onClick={handleConfirm}
          disabled={busy}
        >
          {busy ? "Working..." : confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}

export function useConfirm() {
  const [state, setState] = React.useState<{
    open: boolean
    options: Omit<ConfirmDialogProps, "open" | "onOpenChange" | "onConfirm">
    resolve: ((value: boolean) => void) | null
  }>({ open: false, options: {}, resolve: null })

  const confirm = React.useCallback(
    (
      options: Omit<ConfirmDialogProps, "open" | "onOpenChange" | "onConfirm">
    ): Promise<boolean> =>
      new Promise((resolve) => {
        setState({ open: true, options, resolve })
      }),
    []
  )

  const dialog = (
    <ConfirmDialog
      open={state.open}
      onOpenChange={(open) => {
        if (!open) {
          state.resolve?.(false)
          setState((s) => ({ ...s, open: false, resolve: null }))
        }
      }}
      onConfirm={() => {
        state.resolve?.(true)
        setState((s) => ({ ...s, open: false, resolve: null }))
      }}
      {...state.options}
    />
  )

  return { confirm, dialog }
}
