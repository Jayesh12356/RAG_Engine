"use client"

import * as React from "react"
import { ExternalLink, FileText, Quote } from "lucide-react"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { cleanPdfName, cn } from "@/lib/utils"
import type { Citation, SourceChunk, TextSpan } from "@/types"

/* -------------------------------------------------------------------------- */
/*  Public API                                                                */
/* -------------------------------------------------------------------------- */

export interface SourceViewerTarget {
  documentId: string
  pdfName: string
  pageNumber?: number
  sectionTitle?: string
  textSpan?: TextSpan | null
  /** Free-form preview text shown above the PDF (chunk excerpt). */
  preview?: string
  /** Score, when available, for badge presentation. */
  score?: number
}

interface SourceViewerContextValue {
  open: (target: SourceViewerTarget) => void
  close: () => void
}

const SourceViewerContext = React.createContext<SourceViewerContextValue | null>(null)

export function useSourceViewer() {
  const ctx = React.useContext(SourceViewerContext)
  if (!ctx) {
    return {
      open: () => undefined,
      close: () => undefined,
    } satisfies SourceViewerContextValue
  }
  return ctx
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                    */
/* -------------------------------------------------------------------------- */

function buildPdfUrl(target: SourceViewerTarget): string {
  const base = `/pdfs/by-id/${encodeURIComponent(target.documentId)}`
  const page = target.pageNumber && target.pageNumber > 0 ? target.pageNumber : 1
  return `${base}#page=${page}&zoom=page-fit&view=FitH`
}

export function citationToTarget(citation: Citation): SourceViewerTarget {
  return {
    documentId: citation.document_id,
    pdfName: citation.pdf_name,
    pageNumber: citation.page_number,
    sectionTitle: citation.section_title,
    textSpan: citation.text_span ?? null,
    score: citation.score,
  }
}

export function sourceToTarget(source: SourceChunk): SourceViewerTarget {
  return {
    documentId: source.chunk_id?.split(":")[0] ?? source.pdf_name,
    pdfName: source.pdf_name,
    pageNumber: source.page_number,
    sectionTitle: source.section_title,
    score: source.score,
    preview: source.text,
  }
}

/* -------------------------------------------------------------------------- */
/*  Provider                                                                  */
/* -------------------------------------------------------------------------- */

export function SourceViewerProvider({ children }: { children: React.ReactNode }) {
  const [target, setTarget] = React.useState<SourceViewerTarget | null>(null)
  const [isOpen, setIsOpen] = React.useState(false)

  const value = React.useMemo<SourceViewerContextValue>(
    () => ({
      open: (t) => {
        setTarget(t)
        setIsOpen(true)
      },
      close: () => setIsOpen(false),
    }),
    [],
  )

  return (
    <SourceViewerContext.Provider value={value}>
      {children}
      <SourceViewerSheet
        target={target}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
      />
    </SourceViewerContext.Provider>
  )
}

/* -------------------------------------------------------------------------- */
/*  Sheet                                                                      */
/* -------------------------------------------------------------------------- */

function SourceViewerSheet({
  target,
  isOpen,
  onOpenChange,
}: {
  target: SourceViewerTarget | null
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}) {
  const url = target ? buildPdfUrl(target) : null

  return (
    <Sheet open={isOpen} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className={cn(
          "flex w-full max-w-3xl flex-col gap-0 overflow-hidden p-0",
          "sm:max-w-2xl lg:max-w-3xl",
        )}
      >
        <SheetHeader className="border-b border-border bg-card/80 px-5 py-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary ring-1 ring-inset ring-primary/25">
              <FileText className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate text-base">
                {target ? cleanPdfName(target.pdfName) : "Source"}
              </SheetTitle>
              <SheetDescription className="truncate text-xs">
                {target?.sectionTitle ? `${target.sectionTitle} · ` : ""}
                {target?.pageNumber ? `Page ${target.pageNumber}` : ""}
              </SheetDescription>
            </div>
            {url ? (
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="hidden gap-1.5 sm:inline-flex"
              >
                <a href={url} target="_blank" rel="noreferrer" aria-label="Open source in a new tab">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>Open</span>
                </a>
              </Button>
            ) : null}
          </div>
          {target?.textSpan?.text ? (
            <SpanQuote span={target.textSpan} />
          ) : target?.preview ? (
            <PreviewBlock text={target.preview} />
          ) : null}
        </SheetHeader>
        <div className="relative flex-1 bg-bg">
          {url ? (
            <iframe
              key={url}
              src={url}
              title={target ? `${cleanPdfName(target.pdfName)} viewer` : "Source viewer"}
              className="h-full w-full"
            />
          ) : (
            <div className="grid h-full place-items-center text-sm text-muted-fg">
              No source selected.
            </div>
          )}
        </div>
        <SheetClose className="sr-only">Close source viewer</SheetClose>
      </SheetContent>
    </Sheet>
  )
}

function SpanQuote({ span }: { span: TextSpan }) {
  if (!span.text) return null
  return (
    <div className="mt-3 rounded-lg border border-primary/25 bg-primary/5 p-3 text-[13px] text-fg/90">
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
        <Quote className="h-3 w-3" />
        Cited span
      </div>
      <blockquote className="line-clamp-4 leading-relaxed text-fg/85">
        {span.text}
      </blockquote>
    </div>
  )
}

function PreviewBlock({ text }: { text: string }) {
  return (
    <div className="mt-3 rounded-lg border border-border bg-muted/40 p-3 text-[13px] text-fg/90">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-fg">
        Preview
      </div>
      <p className="line-clamp-4 leading-relaxed text-fg/80">{text}</p>
    </div>
  )
}
