"use client"

import * as React from "react"
import {
  BookmarkPlus,
  Check,
  Copy,
  Download,
  GitBranch,
  Link2,
  MoreHorizontal,
  Printer,
  RefreshCcw,
  Volume2,
  VolumeX,
} from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { useBookmarks } from "@/hooks/use-bookmarks"
import { useSpeechSynthesis } from "@/hooks/use-speech-synthesis"
import { cn } from "@/lib/utils"
import type { Citation, SourceChunk } from "@/types"

export interface AnswerToolbarProps {
  /** Markdown answer content. */
  content: string
  /** Original question, used for share titles and the bookmark payload. */
  question?: string
  /** Sources to include in the markdown export. */
  sources?: SourceChunk[] | null
  /** Citations included in the markdown export. */
  citations?: Citation[] | null
  /** Optional bookmark id (turn id, response id…). */
  bookmarkId?: string
  /** Optional share-link target id (turn id or response id). */
  shareId?: string
  /** Optional fork-from-here handler. */
  onBranch?: () => void
  onRegenerate?: () => void
  onCopy?: (text: string) => void
  /** When true, disables actions that require an idle answer. */
  streaming?: boolean
  className?: string
}

function buildMarkdownExport({
  question,
  content,
  sources,
  citations,
}: Pick<AnswerToolbarProps, "question" | "content" | "sources" | "citations">): string {
  const lines: string[] = []
  if (question) {
    lines.push(`# ${question.replace(/\s+/g, " ").trim()}`)
    lines.push("")
  }
  lines.push(content.trim())
  lines.push("")
  if (citations && citations.length > 0) {
    lines.push("## Citations")
    citations.forEach((c, idx) => {
      const label = c.pdf_name || c.document_id || `Source ${idx + 1}`
      const page = c.page_number ? ` p.${c.page_number}` : ""
      lines.push(`${idx + 1}. ${label}${page}`)
    })
    lines.push("")
  }
  if (sources && sources.length > 0) {
    lines.push("## Sources")
    sources.forEach((s, idx) => {
      const label = s.pdf_name || `Source ${idx + 1}`
      const page = s.page_number ? ` p.${s.page_number}` : ""
      lines.push(`- ${label}${page}`)
    })
    lines.push("")
  }
  lines.push(`_Exported from RAG Engine on ${new Date().toLocaleString()}_`)
  return lines.join("\n")
}

function downloadAsFile(filename: string, content: string, mime = "text/markdown") {
  if (typeof window === "undefined") return
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

function printAnswerAsPdf({
  question,
  content,
  sources,
  citations,
}: Pick<AnswerToolbarProps, "question" | "content" | "sources" | "citations">) {
  if (typeof window === "undefined") return
  const printWindow = window.open("", "_blank", "width=900,height=700")
  if (!printWindow) {
    toast.error("Allow pop-ups to export as PDF")
    return
  }

  const sourcesHtml =
    sources && sources.length
      ? `<section><h2>Sources</h2><ul>${sources
          .map((s) => {
            const label = escapeHtml(s.pdf_name || "Source")
            const page = s.page_number ? ` p.${s.page_number}` : ""
            return `<li>${label}${page}</li>`
          })
          .join("")}</ul></section>`
      : ""

  const citationsHtml =
    citations && citations.length
      ? `<section><h2>Citations</h2><ol>${citations
          .map((c) => {
            const label = escapeHtml(c.pdf_name || c.document_id || "Source")
            const page = c.page_number ? ` p.${c.page_number}` : ""
            const span = c.text_span?.text ? `<blockquote>${escapeHtml(c.text_span.text)}</blockquote>` : ""
            return `<li><strong>${label}</strong>${page}${span}</li>`
          })
          .join("")}</ol></section>`
      : ""

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(question ?? "RAG Engine answer")}</title>
<style>
  :root { color-scheme: light; }
  body { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; color: #111; line-height: 1.6; padding: 32px; max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin-bottom: 24px; }
  h2 { font-size: 16px; margin-top: 24px; }
  pre, code { font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, "SF Mono", monospace; }
  pre { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }
  blockquote { border-left: 3px solid #d0d0d0; padding-left: 12px; color: #555; }
  ul, ol { padding-left: 24px; }
  footer { margin-top: 40px; color: #777; font-size: 12px; }
  @media print { body { padding: 16px; } }
</style>
</head>
<body>
${question ? `<h1>${escapeHtml(question)}</h1>` : ""}
<article>${escapeHtml(content).replace(/\n/g, "<br/>")}</article>
${citationsHtml}
${sourcesHtml}
<footer>Exported from RAG Engine on ${escapeHtml(new Date().toLocaleString())}</footer>
<script>window.addEventListener("load", () => { window.focus(); window.print(); });<\/script>
</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
}

async function copyShareLink(shareId: string | undefined): Promise<void> {
  if (typeof window === "undefined") return
  const url = new URL(window.location.href)
  if (shareId) url.searchParams.set("answer", shareId)
  await navigator.clipboard.writeText(url.toString())
}

export function AnswerToolbar({
  content,
  question,
  sources,
  citations,
  bookmarkId,
  shareId,
  onBranch,
  onRegenerate,
  onCopy,
  streaming,
  className,
}: AnswerToolbarProps) {
  const [copied, setCopied] = React.useState(false)
  const speech = useSpeechSynthesis()
  const { isBookmarked, toggleBookmark } = useBookmarks()
  const bookmarked = bookmarkId ? isBookmarked(bookmarkId) : false

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      onCopy?.(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch {
      toast.error("Could not copy")
    }
  }

  const handleSpeak = () => {
    if (!speech.supported) {
      toast.message("Read-aloud is not supported in this browser")
      return
    }
    speech.toggle(content)
  }

  const handleShare = async () => {
    try {
      await copyShareLink(shareId)
      toast.success("Share link copied to clipboard")
    } catch {
      toast.error("Could not copy share link")
    }
  }

  const handleExportMarkdown = () => {
    const exportContent = buildMarkdownExport({ question, content, sources, citations })
    const safeBase = (question || "answer")
      .replace(/[^a-zA-Z0-9-_ ]+/g, "")
      .replace(/\s+/g, "-")
      .slice(0, 60)
      .toLowerCase() || "answer"
    downloadAsFile(`${safeBase}.md`, exportContent)
    toast.success("Markdown exported")
  }

  const handleExportPdf = () => {
    printAnswerAsPdf({ question, content, sources, citations })
  }

  const handleBookmark = () => {
    if (!bookmarkId || !content) {
      toast.message("Nothing to bookmark yet")
      return
    }
    const wasBookmarked = bookmarked
    toggleBookmark({
      id: bookmarkId,
      question: question || content.slice(0, 80),
      answer: content,
    })
    toast.success(wasBookmarked ? "Bookmark removed" : "Bookmarked")
  }

  return (
    <TooltipProvider delayDuration={250}>
      <div className={cn("flex items-center gap-1", className)}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={handleCopy}
              className="h-7 w-7 text-muted-fg hover:text-fg"
              aria-label="Copy answer"
              disabled={!content}
            >
              {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">Copy</TooltipContent>
        </Tooltip>

        {speech.supported && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={handleSpeak}
                className="h-7 w-7 text-muted-fg hover:text-fg"
                aria-label={speech.speaking ? "Stop reading" : "Read aloud"}
                aria-pressed={speech.speaking}
                disabled={!content}
              >
                {speech.speaking ? (
                  <VolumeX className="h-3.5 w-3.5 text-primary" />
                ) : (
                  <Volume2 className="h-3.5 w-3.5" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">{speech.speaking ? "Stop" : "Read aloud"}</TooltipContent>
          </Tooltip>
        )}

        {onBranch && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={onBranch}
                className="h-7 w-7 text-muted-fg hover:text-fg"
                aria-label="Branch from this answer"
                disabled={streaming}
              >
                <GitBranch className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Branch from here</TooltipContent>
          </Tooltip>
        )}

        {onRegenerate && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={onRegenerate}
                className="h-7 w-7 text-muted-fg hover:text-fg"
                aria-label="Regenerate answer"
                disabled={streaming}
              >
                <RefreshCcw className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Regenerate</TooltipContent>
          </Tooltip>
        )}

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={handleBookmark}
              className={cn("h-7 w-7 text-muted-fg hover:text-fg", bookmarked && "text-primary")}
              aria-label={bookmarked ? "Remove bookmark" : "Bookmark"}
              aria-pressed={bookmarked}
              disabled={!content}
            >
              <BookmarkPlus className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">{bookmarked ? "Bookmarked" : "Bookmark"}</TooltipContent>
        </Tooltip>

        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="h-7 w-7 text-muted-fg hover:text-fg"
                  aria-label="More actions"
                  disabled={!content}
                >
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent side="top">More</TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="end" className="min-w-[200px]">
            <DropdownMenuItem onClick={handleShare}>
              <Link2 className="h-3.5 w-3.5" />
              Copy share link
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleExportMarkdown}>
              <Download className="h-3.5 w-3.5" />
              Export markdown
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleExportPdf}>
              <Printer className="h-3.5 w-3.5" />
              Export PDF
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </TooltipProvider>
  )
}
