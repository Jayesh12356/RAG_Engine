"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { ExternalLink, FileText } from "lucide-react"
import { cleanPdfName, cn } from "@/lib/utils"
import type { SourceChunk } from "@/types"
import { sourceToTarget, useSourceViewer } from "./source-viewer"

export interface SourceLinkProps {
  sources: SourceChunk[] | null | undefined
  className?: string
}

function pickTop(sources: SourceChunk[] | null | undefined): SourceChunk | null {
  if (!sources || sources.length === 0) return null
  return sources.reduce((best, cur) => ((cur.score ?? 0) > (best.score ?? 0) ? cur : best), sources[0])
}

export function SourceLink({ sources, className }: SourceLinkProps) {
  const sourceViewer = useSourceViewer()
  const top = React.useMemo(() => pickTop(sources), [sources])
  if (!top) return null

  const fileLabel = cleanPdfName(top.pdf_name)
  const pageHint = top.page_number ? `p.${top.page_number}` : null

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    sourceViewer.open(sourceToTarget(top))
  }

  return (
    <motion.button
      type="button"
      onClick={handleClick}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -1 }}
      className={cn(
        "group inline-flex max-w-full items-center gap-2.5 rounded-full border border-border bg-card/85 px-3.5 py-1.5 text-[13px] font-medium text-fg shadow-card backdrop-blur-sm transition-all duration-200",
        "hover:border-primary/45 hover:bg-card hover:shadow-glow",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
        className,
      )}
      aria-label={`Open source document: ${fileLabel}`}
    >
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-inset ring-primary/25">
        <FileText className="h-3.5 w-3.5" />
      </span>
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="whitespace-nowrap text-fg">Open source document</span>
        <span className="hidden h-3 w-px bg-border sm:inline-block" aria-hidden />
        <span className="hidden min-w-0 items-center gap-1 text-[12px] text-muted-fg sm:inline-flex">
          <span className="max-w-[280px] truncate" title={fileLabel}>{fileLabel}</span>
          {pageHint ? (
            <span className="text-muted-fg/70">·&nbsp;{pageHint}</span>
          ) : null}
        </span>
      </span>
      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-fg transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
    </motion.button>
  )
}
