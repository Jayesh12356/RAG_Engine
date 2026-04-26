"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { FilesIcon, Search } from "lucide-react"
import { toast } from "sonner"
import { UploadZone } from "@/components/documents/upload-zone"
import { DocCard } from "@/components/documents/doc-card"
import { InspectSheet } from "@/components/documents/inspect-sheet"
import { DeleteDocumentDialog } from "@/components/documents/delete-dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { deleteDocument, getDocuments } from "@/lib/api"
import type { DocumentListItem } from "@/types"
import { Stagger, StaggerItem } from "@/components/motion/stagger"

export default function DocumentsPage() {
  const [docs, setDocs] = React.useState<DocumentListItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [search, setSearch] = React.useState("")
  const [inspectDoc, setInspectDoc] = React.useState<DocumentListItem | null>(null)
  const [inspectOpen, setInspectOpen] = React.useState(false)
  const [deleteDoc, setDeleteDoc] = React.useState<DocumentListItem | null>(null)
  const [deleteOpen, setDeleteOpen] = React.useState(false)
  const [deleting, setDeleting] = React.useState(false)

  const refresh = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await getDocuments()
      setDocs(res.documents ?? [])
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load documents"
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    refresh()
  }, [refresh])

  const filtered = React.useMemo(() => {
    const q = search.toLowerCase().trim()
    if (!q) return docs
    return docs.filter(
      (d) =>
        d.pdf_name.toLowerCase().includes(q) ||
        d.service_name?.toLowerCase().includes(q),
    )
  }, [docs, search])

  const handleConfirmDelete = async () => {
    if (!deleteDoc) return
    setDeleting(true)
    try {
      await deleteDocument(deleteDoc.document_id)
      toast.success(`Deleted ${deleteDoc.pdf_name}`)
      setDocs((prev) => prev.filter((d) => d.document_id !== deleteDoc.document_id))
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed"
      toast.error(message)
    } finally {
      setDeleting(false)
      setDeleteOpen(false)
      setDeleteDoc(null)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-6xl px-6 py-10">
        <motion.header
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-wrap items-end justify-between gap-4"
        >
          <div className="flex items-start gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
              <FilesIcon className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-3xl font-bold tracking-[-0.025em] text-fg">Documents</h1>
              <p className="text-sm text-muted-fg">
                Upload and manage every source the assistant can cite.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {docs.length > 0 && (
              <Badge variant="primary">
                {docs.length} {docs.length === 1 ? "document" : "documents"}
              </Badge>
            )}
          </div>
        </motion.header>

        <div className="mt-8">
          <UploadZone onSuccess={refresh} />
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-[-0.015em] text-fg">Indexed library</h2>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-fg" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter documents…"
              className="h-9 w-[260px] rounded-md border border-border bg-card pl-9 pr-3 text-[13px] outline-none transition-all placeholder:text-muted-fg focus:border-ring focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-bg"
            />
          </div>
        </div>

        {loading ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[140px] w-full rounded-2xl" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-border bg-card/40 p-12 text-center">
            <FilesIcon className="mx-auto mb-2 h-6 w-6 text-muted-fg" />
            <p className="font-medium text-fg">
              {docs.length === 0 ? "No documents yet" : "No matches"}
            </p>
            <p className="mt-1 text-xs text-muted-fg">
              {docs.length === 0
                ? "Upload your first document above to get started."
                : "Try a different search term."}
            </p>
          </div>
        ) : (
          <Stagger
            once={false}
            className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
          >
            {filtered.map((doc) => (
              <StaggerItem key={doc.document_id}>
                <DocCard
                  doc={doc}
                  onInspect={(d) => {
                    setInspectDoc(d)
                    setInspectOpen(true)
                  }}
                  onDelete={(d) => {
                    setDeleteDoc(d)
                    setDeleteOpen(true)
                  }}
                />
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </div>

      <InspectSheet open={inspectOpen} onOpenChange={setInspectOpen} document={inspectDoc} />
      <DeleteDocumentDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        doc={deleteDoc}
        onConfirm={handleConfirmDelete}
        busy={deleting}
      />
    </div>
  )
}
