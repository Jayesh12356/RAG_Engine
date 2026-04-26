"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { AlertTriangle, ChevronDown, ChevronRight, Info, Pause, Play, ScrollText, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getRecentLogs, type LogEntryItem } from "@/lib/api"

const LEVELS = ["all", "info", "warning", "error"] as const
type Level = (typeof LEVELS)[number]

const POLL_MS = 5_000

function levelClasses(level: string) {
  const v = (level || "").toLowerCase()
  if (v === "error") return "border-rose-500/40 bg-rose-500/10 text-rose-200"
  if (v === "warning" || v === "warn") return "border-amber-500/40 bg-amber-500/10 text-amber-200"
  return "border-primary/30 bg-primary/10 text-primary"
}

function levelIcon(level: string) {
  const v = (level || "").toLowerCase()
  if (v === "error") return <AlertTriangle className="h-3 w-3" />
  if (v === "warning" || v === "warn") return <Sparkles className="h-3 w-3" />
  return <Info className="h-3 w-3" />
}

function formatRelative(ts: number): string {
  if (!ts) return "—"
  const ms = ts < 1e12 ? ts * 1000 : ts
  const diff = Date.now() - ms
  if (diff < 1000) return "just now"
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return new Date(ms).toLocaleString()
}

export function RecentActivityTab() {
  const [entries, setEntries] = React.useState<LogEntryItem[]>([])
  const [level, setLevel] = React.useState<Level>("all")
  const [paused, setPaused] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [openSeq, setOpenSeq] = React.useState<number | null>(null)

  const fetchOnce = React.useCallback(async () => {
    try {
      const data = await getRecentLogs(200, level === "all" ? undefined : level)
      setEntries(data.entries.slice().reverse())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load logs")
    }
  }, [level])

  React.useEffect(() => {
    fetchOnce()
  }, [fetchOnce])

  React.useEffect(() => {
    if (paused) return
    const id = window.setInterval(fetchOnce, POLL_MS)
    return () => window.clearInterval(id)
  }, [fetchOnce, paused])

  return (
    <section className="rounded-2xl border border-border bg-card/60 p-5 shadow-card">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-md border border-border bg-bg text-primary">
            <ScrollText className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-fg">Recent activity</h2>
            <p className="text-[11px] text-muted-fg">
              Live tail of structured backend events. Polling every {POLL_MS / 1000}s.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-1 rounded-full border border-border bg-bg p-0.5 text-[11px]">
            {LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLevel(l)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide transition-colors",
                  level === l
                    ? "bg-primary/20 text-primary"
                    : "text-muted-fg hover:text-fg",
                )}
              >
                {l}
              </button>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPaused((p) => !p)}
            className="text-muted-fg"
          >
            {paused ? (
              <>
                <Play className="h-3 w-3" /> Resume
              </>
            ) : (
              <>
                <Pause className="h-3 w-3" /> Pause
              </>
            )}
          </Button>
        </div>
      </header>

      {error && (
        <div className="mt-4 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
          {error}
        </div>
      )}

      <ul className="mt-4 max-h-[420px] space-y-1.5 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {entries.length === 0 && !error && (
            <motion.li
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="rounded-md border border-dashed border-border px-3 py-6 text-center text-xs text-muted-fg"
            >
              No log events yet. Issue a query or upload a document to populate this view.
            </motion.li>
          )}
          {entries.map((entry) => {
            const isOpen = openSeq === entry.seq
            return (
              <motion.li
                key={entry.seq}
                layout
                initial={{ opacity: 0, y: -2 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-md border border-border bg-bg/70"
              >
                <button
                  type="button"
                  onClick={() => setOpenSeq(isOpen ? null : entry.seq)}
                  className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-[12px]"
                >
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      levelClasses(entry.level),
                    )}
                  >
                    {levelIcon(entry.level)}
                    {entry.level}
                  </span>
                  <span className="font-mono text-[12px] text-fg">
                    {entry.event || "(unnamed)"}
                  </span>
                  <span className="ml-auto inline-flex items-center gap-2 text-[11px] text-muted-fg">
                    {entry.extra.request_id ? (
                      <Badge variant="outline" className="text-[10px]">
                        {String(entry.extra.request_id).slice(0, 8)}
                      </Badge>
                    ) : null}
                    <span>{formatRelative(entry.ts)}</span>
                    {isOpen ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </span>
                </button>
                {isOpen && (
                  <pre className="max-h-64 overflow-auto rounded-b-md border-t border-border bg-card/60 px-3 py-2 text-[11px] text-muted-fg">
                    {JSON.stringify(entry.extra, null, 2)}
                  </pre>
                )}
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>
    </section>
  )
}
