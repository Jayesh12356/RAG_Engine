"use client"

import { motion } from "framer-motion"
import { Calendar, FileText, Layers, MoreHorizontal, Trash2, Eye } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { formatDate } from "@/lib/utils"
import type { DocumentListItem } from "@/types"

export function DocCard({
  doc,
  onInspect,
  onDelete,
}: {
  doc: DocumentListItem
  onInspect: (doc: DocumentListItem) => void
  onDelete: (doc: DocumentListItem) => void
}) {
  return (
    <motion.article
      layout
      variants={{
        hidden: { opacity: 0, y: 12 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
      }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
      className="group relative flex cursor-pointer flex-col gap-3 rounded-2xl border border-border bg-card/85 p-5 shadow-card transition-shadow hover:shadow-glow"
      onClick={() => onInspect(doc)}
    >
      <header className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110">
          <FileText className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 text-sm font-semibold leading-tight text-fg">
            {doc.pdf_name}
          </h3>
          <p className="mt-1 text-xs text-muted-fg">{doc.service_name || "General"}</p>
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
      <div className="flex flex-wrap items-center gap-2">
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
