"use client"

import { AlertTriangle } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import type { DocumentListItem } from "@/types"

export function DeleteDocumentDialog({
  open,
  onOpenChange,
  doc,
  onConfirm,
  busy,
}: {
  open: boolean
  onOpenChange: (next: boolean) => void
  doc: DocumentListItem | null
  onConfirm: () => void
  busy: boolean
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full bg-danger/10 text-danger">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <DialogTitle>Delete document?</DialogTitle>
          <DialogDescription>
            This permanently removes
            <span className="mx-1 font-semibold text-fg">{doc?.pdf_name}</span>
            and its {doc?.total_chunks ?? 0} indexed chunks. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" variant="danger" onClick={onConfirm} disabled={busy}>
            {busy ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
