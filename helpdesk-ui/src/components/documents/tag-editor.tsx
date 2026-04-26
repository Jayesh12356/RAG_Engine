"use client"

import * as React from "react"
import { Plus, X } from "lucide-react"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { setDocumentTags } from "@/lib/api"
import type { DocumentListItem } from "@/types"

export interface TagEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  doc: DocumentListItem | null
  knownTags: string[]
  onSaved: (doc: DocumentListItem, tags: string[]) => void
}

export function TagEditor({ open, onOpenChange, doc, knownTags, onSaved }: TagEditorProps) {
  const [draft, setDraft] = React.useState<string[]>([])
  const [pending, setPending] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    setDraft(doc?.tags ?? [])
    setPending("")
  }, [doc])

  const suggestions = React.useMemo(
    () => knownTags.filter((t) => !draft.some((d) => d.toLowerCase() === t.toLowerCase())),
    [knownTags, draft],
  )

  const addTag = (raw: string) => {
    const value = raw.trim().slice(0, 32)
    if (!value) return
    if (draft.some((t) => t.toLowerCase() === value.toLowerCase())) return
    if (draft.length >= 16) {
      toast.error("Up to 16 tags per document")
      return
    }
    setDraft([...draft, value])
    setPending("")
  }

  const removeTag = (value: string) => {
    setDraft(draft.filter((t) => t !== value))
  }

  const handleSave = async () => {
    if (!doc) return
    setSaving(true)
    try {
      const res = await setDocumentTags(doc.document_id, draft)
      onSaved(doc, res.tags)
      toast.success("Tags updated")
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save tags")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Spaces & tags</DialogTitle>
          <DialogDescription>
            Group {doc?.pdf_name ?? "this document"} into one or more Spaces. Tags become a Qdrant filter at
            query time.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <div className="flex flex-wrap gap-1.5 rounded-md border border-border bg-card/40 p-2 min-h-[44px]">
            {draft.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs text-primary"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="rounded-full text-primary/70 hover:text-primary"
                  aria-label={`Remove ${tag}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            {!draft.length && (
              <span className="text-xs text-muted-fg">No tags yet — add one below.</span>
            )}
          </div>

          <div className="flex gap-2">
            <Input
              value={pending}
              onChange={(e) => setPending(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  addTag(pending)
                }
              }}
              placeholder="New tag (e.g. legal, product, q3-revenue)"
            />
            <Button type="button" variant="outline" onClick={() => addTag(pending)}>
              <Plus className="h-3.5 w-3.5" />
              Add
            </Button>
          </div>

          {suggestions.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-muted-fg">Suggestions</p>
              <div className="flex flex-wrap gap-1.5">
                {suggestions.slice(0, 12).map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => addTag(tag)}
                    className="rounded-full border border-border bg-card px-2 py-0.5 text-xs text-muted-fg transition-colors hover:border-primary/40 hover:text-fg"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            Save tags
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
