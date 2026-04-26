"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Check, FileUp, Sparkles } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { postIngest } from "@/lib/api"
import { cn } from "@/lib/utils"

// Mirror of app/ingestion/router.py SUPPORTED_EXTENSIONS — keep in sync.
const ACCEPT = [
  // Documents
  "application/pdf",
  ".pdf",
  ".docx",
  ".pptx",
  // Spreadsheets / data
  ".xlsx",
  ".xls",
  ".csv",
  // Text / web / data
  ".txt",
  ".md",
  ".markdown",
  ".html",
  ".htm",
  ".json",
  // Images (OCR + vision)
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".tiff",
  ".tif",
  ".bmp",
].join(",")

export function UploadZone({ onSuccess }: { onSuccess: () => void }) {
  const [demoMode, setDemoMode] = React.useState(false)
  const [override, setOverride] = React.useState("")
  const [drag, setDrag] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [progress, setProgress] = React.useState(0)
  const [done, setDone] = React.useState(false)
  const fileRef = React.useRef<HTMLInputElement>(null)

  const ingest = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const list = Array.from(files)
    setBusy(true)
    setDone(false)
    setProgress(8)
    try {
      // Faux-progress while waiting for server response (FormData fetch has no progress)
      const tick = window.setInterval(() => {
        setProgress((p) => Math.min(p + Math.random() * 14, 90))
      }, 220)
      for (const file of list) {
        const res = await postIngest(file, override || undefined, undefined, demoMode)
        toast.success(`Ingested ${res.pdf_name}`, {
          description: `${res.total_pages} pages • ${res.total_chunks} chunks indexed`,
        })
      }
      window.clearInterval(tick)
      setProgress(100)
      setDone(true)
      onSuccess()
      window.setTimeout(() => {
        setBusy(false)
        setProgress(0)
        setDone(false)
      }, 1400)
    } catch (err) {
      setBusy(false)
      setProgress(0)
      const message = err instanceof Error ? err.message : "Ingest failed"
      toast.error(message)
    }
  }

  return (
    <div
      data-tour="upload-zone"
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        ingest(e.dataTransfer.files)
      }}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-dashed border-border bg-card/60 p-8 transition-colors",
        drag && "border-primary/50 bg-primary/5",
      )}
    >
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="relative flex h-14 w-14 items-center justify-center">
          <AnimatePresence mode="wait">
            {done ? (
              <motion.div
                key="success"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.6, opacity: 0 }}
                className="grid h-14 w-14 place-items-center rounded-full bg-success/15 ring-2 ring-success/40"
              >
                <Check className="h-6 w-6 text-success" />
              </motion.div>
            ) : busy ? (
              <motion.svg
                key="ring"
                width={56}
                height={56}
                viewBox="0 0 56 56"
                className="-rotate-90"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <circle cx={28} cy={28} r={24} stroke="hsl(var(--border))" strokeWidth={4} fill="transparent" />
                <motion.circle
                  cx={28}
                  cy={28}
                  r={24}
                  stroke="url(#u-gradient)"
                  strokeWidth={4}
                  fill="transparent"
                  strokeLinecap="round"
                  strokeDasharray={2 * Math.PI * 24}
                  animate={{ strokeDashoffset: 2 * Math.PI * 24 * (1 - progress / 100) }}
                  transition={{ duration: 0.4 }}
                />
                <defs>
                  <linearGradient id="u-gradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="hsl(var(--primary))" />
                    <stop offset="100%" stopColor="hsl(var(--accent))" />
                  </linearGradient>
                </defs>
              </motion.svg>
            ) : (
              <motion.div
                key="idle"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
                className="grid h-14 w-14 place-items-center rounded-2xl border border-border bg-card text-primary shadow-card"
              >
                <FileUp className="h-6 w-6" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <h3 className="text-2xl font-semibold tracking-[-0.02em] text-fg">
          {busy ? "Ingesting…" : done ? "All set!" : "Upload to your workspace"}
        </h3>
        <p className="max-w-md text-sm text-muted-fg">
          Drag &amp; drop PDFs, Word, PowerPoint, Excel/CSV, text, Markdown, HTML, JSON or images.
          We extract, chunk and embed them so you can query in seconds.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            size="md"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Choose files
          </Button>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              ingest(e.target.files)
              e.target.value = ""
            }}
          />
          <input
            value={override}
            onChange={(e) => setOverride(e.target.value)}
            placeholder="Service name (optional)"
            className="h-9 rounded-md border border-border bg-card px-3 text-[12px] text-fg outline-none placeholder:text-muted-fg/80 focus-visible:ring-2 focus-visible:ring-ring"
          />
          <label className="flex items-center gap-2 text-xs font-medium text-muted-fg">
            <Switch checked={demoMode} onCheckedChange={setDemoMode} aria-label="Demo mode" />
            Demo
          </label>
        </div>
      </div>
      {drag && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl bg-primary/5"
          style={{ boxShadow: "inset 0 0 0 2px hsl(var(--primary))" }}
        />
      )}
    </div>
  )
}

export function UploadZoneInline({ onSelect }: { onSelect: (file: File) => void }) {
  const ref = React.useRef<HTMLInputElement>(null)
  return (
    <Button type="button" variant="secondary" size="sm" onClick={() => ref.current?.click()}>
      <FileUp className="h-3.5 w-3.5" />
      Upload
      <input
        ref={ref}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onSelect(f)
          e.target.value = ""
        }}
      />
    </Button>
  )
}
