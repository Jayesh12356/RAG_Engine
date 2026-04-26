"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { FileText, Hash, Loader2, RefreshCcw } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getDocumentChunks } from "@/lib/api"
import type { DocumentListItem } from "@/types"
import { toast } from "sonner"

interface ChunkRow {
  chunk_id: string
  text: string
  section_title?: string
  page_number?: number
  [key: string]: unknown
}

export function InspectSheet({
  open,
  onOpenChange,
  document,
}: {
  open: boolean
  onOpenChange: (next: boolean) => void
  document: DocumentListItem | null
}) {
  const [chunks, setChunks] = React.useState<ChunkRow[]>([])
  const [loading, setLoading] = React.useState(false)

  const load = React.useCallback(async () => {
    if (!document) return
    setLoading(true)
    try {
      const data = await getDocumentChunks(document.document_id)
      setChunks((data.chunks ?? []) as ChunkRow[])
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch chunks"
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [document])

  React.useEffect(() => {
    if (open && document) load()
    if (!open) setChunks([])
  }, [open, document, load])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-lg">
        <SheetHeader className="border-b border-border p-5">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-muted text-primary">
              <FileText className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate">{document?.pdf_name}</SheetTitle>
              <SheetDescription>
                {document
                  ? `${document.total_chunks} chunks across ${document.total_pages} pages.`
                  : "Select a document to inspect."}
              </SheetDescription>
            </div>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onClick={load}
              disabled={loading}
              aria-label="Refresh chunks"
            >
              <RefreshCcw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            </Button>
          </div>
        </SheetHeader>
        <ScrollArea className="flex-1">
          <div className="flex flex-col gap-3 p-5">
            {loading ? (
              <div className="flex items-center gap-2 rounded-md border border-border bg-card/60 p-4 text-sm text-muted-fg">
                <Loader2 className="h-4 w-4 animate-spin" />
                Fetching chunks…
              </div>
            ) : chunks.length === 0 ? (
              <p className="rounded-md border border-dashed border-border bg-card/40 p-4 text-center text-xs text-muted-fg">
                No chunks indexed for this document yet.
              </p>
            ) : (
              chunks.map((chunk, i) => (
                <motion.div
                  key={chunk.chunk_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.02, 0.4), duration: 0.25 }}
                  className="rounded-md border border-border bg-card/70 p-4 shadow-card"
                >
                  <header className="flex items-center justify-between gap-2 text-[11px] text-muted-fg">
                    <Badge variant="outline">
                      <Hash className="h-3 w-3" />#{i + 1}
                    </Badge>
                    <span>
                      {chunk.section_title || "Untitled"} • Page {chunk.page_number ?? "?"}
                    </span>
                  </header>
                  <p className="mt-2 line-clamp-[10] whitespace-pre-wrap text-[13px] leading-relaxed text-fg/90">
                    {chunk.text}
                  </p>
                </motion.div>
              ))
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
