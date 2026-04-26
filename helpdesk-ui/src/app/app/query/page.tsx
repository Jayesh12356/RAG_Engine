"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AlertCircle, Loader2, Send, Sparkles } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import { ConfidenceGauge } from "@/components/chat/confidence-gauge"
import { MarkdownAnswer } from "@/components/answer/markdown-answer"
import { SourceLink } from "@/components/answer/source-link"
import { useTypewriter } from "@/components/query/typewriter"
import { GlowOrb } from "@/components/motion/glow-orb"
import { postQueryStream } from "@/lib/api"
import type { QueryResponse } from "@/types"
import { cn } from "@/lib/utils"

const PHRASES = [
  "What was Q3 revenue?",
  "Summarize the security policy in three bullet points.",
  "Who owns the customer-success roadmap?",
  "Compare onboarding flows for new hires across regions.",
  "List unresolved risks in the latest engineering memo.",
]

const RECENT_KEY = "rag_engine.recent_queries"
const MAX_RECENT = 5

function loadRecent(): string[] {
  if (typeof window === "undefined") return []
  try {
    return JSON.parse(window.localStorage.getItem(RECENT_KEY) || "[]") as string[]
  } catch {
    return []
  }
}
function saveRecent(items: string[]) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, MAX_RECENT)))
}

const CATEGORIES = ["GENERAL", "VPN", "SSL", "EMAIL", "NETWORK", "OTHER"] as const

export default function QueryPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialQuestion = searchParams.get("q") ?? ""

  const [question, setQuestion] = React.useState(initialQuestion)
  const [category, setCategory] = React.useState("GENERAL")
  const [demoMode, setDemoMode] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [response, setResponse] = React.useState<QueryResponse | null>(null)
  const [streamAnswer, setStreamAnswer] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [recent, setRecent] = React.useState<string[]>([])

  const placeholder = useTypewriter(PHRASES)

  React.useEffect(() => {
    setRecent(loadRecent())
  }, [])

  const submit = React.useCallback(
    async (text?: string) => {
      const q = (text ?? question).trim()
      if (!q) return
      setLoading(true)
      setError(null)
      setResponse(null)
      setStreamAnswer("")
      try {
        const res = await postQueryStream(
          q,
          (delta) => setStreamAnswer((prev) => prev + delta),
          category,
          demoMode,
        )
        setResponse(res)
        const next = [q, ...recent.filter((r) => r !== q)].slice(0, MAX_RECENT)
        setRecent(next)
        saveRecent(next)
        if (text && text !== question) setQuestion(text)
      } catch (err) {
        const message = err instanceof Error ? err.message : "Query failed"
        setError(message)
        toast.error(message)
      } finally {
        setLoading(false)
      }
    },
    [question, category, demoMode, recent],
  )

  React.useEffect(() => {
    if (initialQuestion) {
      submit(initialQuestion)
      // Clear from URL after firing once
      router.replace("/app/query")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submit()
  }

  return (
    <div className="relative h-full overflow-y-auto">
      <div className="pointer-events-none absolute inset-0 -z-0">
        <GlowOrb
          size={520}
          color="hsl(var(--primary) / 0.22)"
          className="left-1/2 top-[-160px] -translate-x-1/2"
          intensity={0.85}
        />
      </div>

      <div className="relative mx-auto w-full max-w-4xl px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="text-center"
        >
          <p className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-fg backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            One-shot grounded answers
          </p>
          <h1 className="mt-4 text-4xl font-bold tracking-[-0.03em] text-fg md:text-5xl">
            Ask. Receive. <span className="text-shimmer">Verify.</span>
          </h1>
          <p className="mt-2 text-sm text-muted-fg">
            Press <span className="font-medium text-fg">Enter</span> or click <em>Ask</em>.
            Every answer ships with citations and a confidence gauge.
          </p>
        </motion.div>

        <form
          onSubmit={handleSubmit}
          className={cn(
            "relative mt-9 rounded-2xl border border-border bg-card/85 p-3 shadow-card backdrop-blur-md transition-shadow",
            "focus-within:border-primary/50 focus-within:shadow-glow",
          )}
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            rows={2}
            placeholder={placeholder + (placeholder ? "▍" : "")}
            className="block w-full resize-none bg-transparent px-4 pt-3 pb-1 text-[15px] text-fg outline-none placeholder:text-muted-fg/80"
          />
          <div className="flex flex-wrap items-center gap-3 border-t border-border/60 px-3 pt-2">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
                Category
              </span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="h-7 rounded-md border border-border bg-card px-2 text-[12px] text-fg outline-none transition-colors hover:border-ring focus-visible:ring-2 focus-visible:ring-ring"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c.charAt(0) + c.slice(1).toLowerCase()}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={demoMode} onCheckedChange={setDemoMode} aria-label="Demo mode" />
              <span className="text-xs font-medium text-muted-fg">Demo</span>
            </div>
            <Button
              type="submit"
              disabled={loading || !question.trim()}
              size="sm"
              className="ml-auto h-9 px-4"
            >
              {loading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Thinking
                </>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  Ask
                </>
              )}
            </Button>
          </div>
        </form>

        {recent.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-4 flex flex-wrap items-center gap-2"
          >
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
              Recent
            </span>
            {recent.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => submit(r)}
                className="group inline-flex max-w-[260px] items-center gap-1 rounded-full border border-border bg-card/60 px-3 py-1 text-xs text-fg transition-all hover:border-primary/40 hover:bg-card hover:shadow-card"
              >
                <span className="truncate">{r}</span>
              </button>
            ))}
          </motion.div>
        )}

        {error && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </motion.div>
        )}

        <AnimatePresence mode="wait">
          {loading && !streamAnswer && (
            <motion.div
              key="loading"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-7 rounded-2xl border border-border bg-card/70 p-6 shadow-card"
            >
              <div className="flex items-start justify-between">
                <Skeleton className="h-7 w-32" />
                <Skeleton className="h-16 w-16 rounded-full" />
              </div>
              <Skeleton className="mt-5 h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-5/6" />
              <Skeleton className="mt-2 h-4 w-3/4" />
            </motion.div>
          )}
          {(streamAnswer || response) && (
            <motion.section
              key="answer"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="mt-7 rounded-2xl border border-border bg-card/85 p-6 shadow-card backdrop-blur-md"
            >
              <header className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
                    Answer
                  </p>
                  <h2 className="mt-1 line-clamp-2 text-2xl font-semibold tracking-[-0.02em] text-fg">
                    {response?.question || question}
                  </h2>
                </div>
                {response ? (
                  <ConfidenceGauge
                    value={response.confidence}
                    refused={response.refused}
                    size={88}
                  />
                ) : (
                  <ConfidenceGauge value={0.5} label="Streaming…" size={88} />
                )}
              </header>

              <div className="mt-5">
                <MarkdownAnswer
                  content={response ? response.answer : streamAnswer}
                  streaming={!response}
                />
                {!response && (
                  <span
                    className="ml-0.5 inline-block h-4 w-[2px] translate-y-[2px] bg-primary animate-blink"
                    aria-hidden
                  />
                )}
              </div>

              {response?.sources?.length ? (
                <div className="mt-7 flex flex-wrap items-center gap-x-3 gap-y-2">
                  <SourceLink sources={response.sources} />
                </div>
              ) : null}
            </motion.section>
          )}
        </AnimatePresence>

        {!loading && !response && !streamAnswer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="mt-12 rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center"
          >
            <Sparkles className="mx-auto h-6 w-6 text-primary" />
            <p className="mt-2 font-medium text-fg">Your answer will appear here</p>
            <p className="mt-1 text-xs text-muted-fg">
              Press Enter or click Ask. Answers stream in token-by-token.
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}
