"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  Calendar,
  Check,
  Copy,
  Eye,
  FileText,
  Hash,
  Layers,
  MoreHorizontal,
  Tag,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cleanFilename, formatDate, shortId } from "@/lib/utils"
import type { DocumentListItem } from "@/types"

export function DocCard({
  doc,
  onInspect,
  onDelete,
  onEditTags,
}: {
  doc: DocumentListItem
  onInspect: (doc: DocumentListItem) => void
  onDelete: (doc: DocumentListItem) => void
  onEditTags?: (doc: DocumentListItem) => void
}) {
  const [copied, setCopied] = React.useState(false)
  const displayName = cleanFilename(doc.pdf_name)
  const idLabel = shortId(doc.document_id)

  async function copyId(event: React.MouseEvent<HTMLButtonElement>) {
    event.stopPropagation()
    try {
      await navigator.clipboard.writeText(doc.document_id)
      setCopied(true)
      toast.success("Document ID copied")
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      toast.error("Could not copy ID")
    }
  }

  return (
    <motion.article
      layout
      draggable
      onDragStart={(e) => {
        const native = e as unknown as React.DragEvent<HTMLDivElement>
        native.dataTransfer.setData("application/x-document-id", doc.document_id)
        native.dataTransfer.effectAllowed = "copy"
      }}
      variants={{
        hidden: { opacity: 0, y: 12 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
      }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
      className="group relative flex h-full min-h-[176px] cursor-pointer flex-col rounded-2xl border border-border bg-card/85 p-5 shadow-card transition-shadow hover:shadow-glow"
      onClick={() => onInspect(doc)}
      title={doc.pdf_name}
    >
      <header className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110">
          <FileText className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 break-words text-sm font-semibold leading-snug text-fg">
            {displayName}
          </h3>
          <button
            type="button"
            onClick={copyId}
            className="mt-1 inline-flex max-w-full items-center gap-1.5 rounded-md px-1 py-0.5 -ml-1 font-mono text-[11px] text-muted-fg transition-colors hover:bg-card hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={`Copy ID — ${doc.document_id}`}
            aria-label={`Copy document id ${doc.document_id}`}
          >
            {copied ? (
              <Check className="h-3 w-3 text-success" />
            ) : (
              <Copy className="h-3 w-3 opacity-60 transition-opacity group-hover:opacity-100" />
            )}
            <span className="truncate">{idLabel}</span>
          </button>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
              onClick={(e) => e.stopPropagation()}
              aria-label="Document actions"
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem onSelect={() => onInspect(doc)}>
              <Eye className="h-3.5 w-3.5 text-muted-fg" />
              Inspect chunks
            </DropdownMenuItem>
            {onEditTags && (
              <DropdownMenuItem onSelect={() => onEditTags(doc)}>
                <Tag className="h-3.5 w-3.5 text-muted-fg" />
                Edit tags
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => onDelete(doc)}
              className="text-danger focus:text-danger"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete document
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      {doc.tags && doc.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {doc.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
            >
              <Hash className="h-2.5 w-2.5" />
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
        <Badge variant="secondary">
          <Layers className="h-3 w-3" />
          {doc.total_chunks.toLocaleString()} chunks
        </Badge>
        <Badge variant="secondary">
          <FileText className="h-3 w-3" />
          {doc.total_pages.toLocaleString()} pages
        </Badge>
        <Badge variant="outline">
          <Calendar className="h-3 w-3" />
          {formatDate(doc.created_at)}
        </Badge>
        {typeof doc.version === "number" && doc.version > 1 && (
          <Badge variant="outline" title="Document version">
            v{doc.version}
          </Badge>
        )}
      </div>

      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: "radial-gradient(120% 60% at 50% 0%, hsl(var(--primary) / 0.08), transparent 60%)",
        }}
      />
    </motion.article>
  )
}
