"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Check, FileUp, Sparkles, X as XIcon, AlertCircle, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { postIngest, streamIngestEvents } from "@/lib/api"
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

interface UploadEntry {
  id: string
  file: File
  progress: number
  stage: string
  status: "queued" | "running" | "complete" | "failed"
  message?: string
  error?: string
}

export function UploadZone({ onSuccess }: { onSuccess: () => void }) {
  const [demoMode, setDemoMode] = React.useState(false)
  const [override, setOverride] = React.useState("")
  const [drag, setDrag] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [entries, setEntries] = React.useState<UploadEntry[]>([])
  const fileRef = React.useRef<HTMLInputElement>(null)

  const updateEntry = React.useCallback((id: string, patch: Partial<UploadEntry>) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)))
  }, [])

  const removeEntry = React.useCallback((id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id))
  }, [])

  const ingest = React.useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return
      const list = Array.from(files)
      setBusy(true)

      const newEntries: UploadEntry[] = list.map((file, i) => ({
        id: `${Date.now()}-${i}-${file.name}`,
        file,
        progress: 0,
        stage: "queued",
        status: "queued",
      }))
      setEntries((prev) => [...newEntries, ...prev])

      try {
        await Promise.all(
          newEntries.map(async (entry) => {
            try {
              updateEntry(entry.id, { progress: 5, stage: "uploading", status: "running" })
              const res = await postIngest(entry.file, override || undefined, true, demoMode)
              if (!res.task_id) {
                updateEntry(entry.id, {
                  progress: 100,
                  stage: "complete",
                  status: "complete",
                  message: `${res.total_pages} pages • ${res.total_chunks} chunks`,
                })
                return
              }
              updateEntry(entry.id, { progress: 12, stage: "queued", status: "running" })
              await streamIngestEvents(res.task_id, (evt) => {
                updateEntry(entry.id, {
                  progress: Math.min(100, evt.progress ?? 0),
                  stage: evt.stage || evt.status,
                  status: (evt.status as UploadEntry["status"]) || "running",
                  message: evt.message ?? undefined,
                  error: evt.error ?? undefined,
                })
              })
              updateEntry(entry.id, { progress: 100, status: "complete" })
              toast.success(`Ingested ${entry.file.name}`)
            } catch (err) {
              const message = err instanceof Error ? err.message : "Ingest failed"
              updateEntry(entry.id, { status: "failed", error: message })
              toast.error(`${entry.file.name}: ${message}`)
            }
          }),
        )
        onSuccess()
      } finally {
        setBusy(false)
        // Auto-cleanup completed entries after a short success window
        window.setTimeout(() => {
          setEntries((prev) => prev.filter((e) => e.status !== "complete"))
        }, 4000)
      }
    },
    [demoMode, override, onSuccess, updateEntry],
  )

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
            {busy ? (
              <motion.div
                key="busy"
                initial={{ scale: 0.85, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.85, opacity: 0 }}
                className="grid h-14 w-14 place-items-center rounded-2xl border border-primary/40 bg-primary/10 text-primary shadow-card"
              >
                <Loader2 className="h-6 w-6 animate-spin" />
              </motion.div>
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
          {busy ? "Ingesting…" : "Upload to your workspace"}
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

      {entries.length > 0 && (
        <div className="mt-6 space-y-2">
          <AnimatePresence initial={false}>
            {entries.map((entry) => (
              <motion.div
                key={entry.id}
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ duration: 0.18 }}
                className={cn(
                  "flex items-center gap-3 rounded-md border border-border bg-card/80 px-3 py-2",
                  entry.status === "failed" && "border-rose-500/40",
                  entry.status === "complete" && "border-success/40",
                )}
              >
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-muted/60 text-muted-fg">
                  {entry.status === "complete" ? (
                    <Check className="h-3.5 w-3.5 text-success" />
                  ) : entry.status === "failed" ? (
                    <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
                  ) : (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate font-medium text-fg">{entry.file.name}</span>
                    <span className="shrink-0 tabular-nums text-muted-fg">
                      {entry.status === "failed"
                        ? "Failed"
                        : entry.status === "complete"
                        ? "Done"
                        : `${Math.round(entry.progress)}%`}
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-muted">
                    <motion.div
                      className={cn(
                        "h-full rounded-full",
                        entry.status === "failed"
                          ? "bg-rose-500"
                          : entry.status === "complete"
                          ? "bg-success"
                          : "bg-gradient-to-r from-primary to-accent",
                      )}
                      initial={{ width: 0 }}
                      animate={{ width: `${entry.progress}%` }}
                      transition={{ duration: 0.25 }}
                    />
                  </div>
                  <p className="mt-1 truncate text-[10.5px] text-muted-fg">
                    {entry.error || entry.message || entry.stage}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeEntry(entry.id)}
                  className="rounded-md p-1 text-muted-fg hover:bg-muted hover:text-fg"
                  aria-label="Dismiss"
                >
                  <XIcon className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
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
