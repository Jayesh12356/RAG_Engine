"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { usePathname, useRouter } from "next/navigation"
import { ArrowRight, Sparkles, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const STORAGE_KEY = "rag_engine.tour_seen"

interface TourStep {
  id: string
  title: string
  description: string
  selector: string
  page: string
  pageLabel: string
  fallbackPosition: "left" | "right" | "center"
}

const STEPS: TourStep[] = [
  {
    id: "sidebar",
    title: "Your workspace",
    description:
      "Hop between Chat, one-shot Query, your Documents, and live System status — all from this sidebar.",
    selector: "[data-tour=\"sidebar\"]",
    page: "/app/chat",
    pageLabel: "Chat",
    fallbackPosition: "right",
  },
  {
    id: "composer",
    title: "Ask anything",
    description:
      "Type a question and watch RAG Engine stream a grounded answer — sources are always one click away.",
    selector: "[data-tour=\"composer\"]",
    page: "/app/chat",
    pageLabel: "Chat",
    fallbackPosition: "center",
  },
  {
    id: "upload",
    title: "Bring your docs",
    description:
      "Drag-drop PDFs, Word, Excel/CSV, PowerPoint, text, Markdown, HTML, JSON or images. We extract, chunk and embed them so you can ask in seconds.",
    selector: "[data-tour=\"upload-zone\"]",
    page: "/app/documents",
    pageLabel: "Documents",
    fallbackPosition: "center",
  },
  {
    id: "status",
    title: "Inspect the engine",
    description:
      "Live latency for every provider — LLM, embeddings, vector + relational DB — so you always know where you stand.",
    selector: "[data-tour=\"status-grid\"]",
    page: "/app/status",
    pageLabel: "Status",
    fallbackPosition: "center",
  },
]

export function OnboardingTour() {
  const [show, setShow] = React.useState(false)
  const [stepIndex, setStepIndex] = React.useState(0)
  const [rect, setRect] = React.useState<DOMRect | null>(null)
  const pathname = usePathname()
  const router = useRouter()

  React.useEffect(() => {
    try {
      const seen = window.localStorage.getItem(STORAGE_KEY)
      if (!seen) {
        const t = window.setTimeout(() => setShow(true), 900)
        return () => window.clearTimeout(t)
      }
    } catch {
      /* ignore */
    }
  }, [])

  const cur = STEPS[stepIndex]
  const onPage = cur ? pathname === cur.page || pathname?.startsWith(`${cur.page}/`) : false

  React.useEffect(() => {
    if (!show || !cur) return
    let raf = 0
    const update = () => {
      const el = document.querySelector(cur.selector) as HTMLElement | null
      if (!el) {
        setRect(null)
        return
      }
      setRect(el.getBoundingClientRect())
    }
    update()
    const id = window.setInterval(() => {
      raf = window.requestAnimationFrame(update)
    }, 350)
    window.addEventListener("resize", update)
    window.addEventListener("scroll", update, true)
    return () => {
      window.clearInterval(id)
      window.cancelAnimationFrame(raf)
      window.removeEventListener("resize", update)
      window.removeEventListener("scroll", update, true)
    }
  }, [show, cur, pathname])

  const dismiss = React.useCallback(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, "1")
    } catch {
      /* ignore */
    }
    setShow(false)
  }, [])

  const next = () => {
    if (stepIndex >= STEPS.length - 1) {
      dismiss()
      return
    }
    setStepIndex((i) => i + 1)
  }

  const back = () => setStepIndex((i) => Math.max(0, i - 1))

  if (!cur) return null

  const showSpotlight = onPage && rect

  const cardPosition = (() => {
    if (!showSpotlight) {
      return { top: "50%", left: "50%", transform: "translate(-50%, -50%)" }
    }
    if (cur.fallbackPosition === "right" && rect.right < window.innerWidth - 360) {
      return { top: rect.top + rect.height / 2 - 90, left: rect.right + 20 }
    }
    const placeBelow = rect.top + rect.height + 280 < window.innerHeight
    return placeBelow
      ? {
          top: Math.min(rect.bottom + 18, window.innerHeight - 240),
          left: Math.min(Math.max(rect.left + rect.width / 2 - 200, 16), window.innerWidth - 416),
        }
      : {
          top: Math.max(rect.top - 220, 16),
          left: Math.min(Math.max(rect.left + rect.width / 2 - 200, 16), window.innerWidth - 416),
        }
  })()

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          key="tour"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-[90]"
          aria-live="polite"
        >
          {showSpotlight ? (
            <motion.div
              key={cur.id}
              layout
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="pointer-events-none absolute rounded-2xl"
              style={{
                top: Math.max(rect.top - 8, 4),
                left: Math.max(rect.left - 8, 4),
                width: rect.width + 16,
                height: rect.height + 16,
                boxShadow: "0 0 0 9999px hsl(var(--bg) / 0.78)",
                outline: "2px solid hsl(var(--primary))",
                outlineOffset: "2px",
              }}
            >
              <span className="absolute inset-0 animate-tour-pulse rounded-2xl" />
            </motion.div>
          ) : (
            <div className="absolute inset-0 bg-bg/85 backdrop-blur-sm" />
          )}

          <motion.div
            key={`${cur.id}-card`}
            initial={{ opacity: 0, y: 8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className={cn(
              "absolute w-[400px] max-w-[calc(100vw-32px)] rounded-2xl border border-border bg-card p-5 shadow-glow",
            )}
            style={cardPosition}
          >
            <header className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/30">
                <Sparkles className="h-4 w-4" />
              </span>
              <div className="flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
                  Step {stepIndex + 1} of {STEPS.length}
                </p>
                <h3 className="mt-0.5 text-xl font-semibold tracking-[-0.015em] text-fg">{cur.title}</h3>
              </div>
              <button
                type="button"
                onClick={dismiss}
                aria-label="Skip tour"
                className="rounded-md p-1 text-muted-fg transition-colors hover:bg-muted hover:text-fg"
              >
                <X className="h-4 w-4" />
              </button>
            </header>
            <p className="mt-3 text-sm leading-relaxed text-muted-fg">{cur.description}</p>
            <div className="mt-4 flex items-center gap-1.5">
              {STEPS.map((_, i) => (
                <span
                  key={i}
                  className={cn(
                    "h-1 rounded-full transition-all",
                    i === stepIndex ? "w-6 bg-primary" : "w-3 bg-muted",
                  )}
                />
              ))}
            </div>
            <footer className="mt-5 flex items-center justify-between gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={dismiss}>
                Skip tour
              </Button>
              <div className="flex items-center gap-2">
                {stepIndex > 0 && (
                  <Button type="button" variant="secondary" size="sm" onClick={back}>
                    Back
                  </Button>
                )}
                {!onPage && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => router.push(cur.page)}
                  >
                    Open {cur.pageLabel}
                  </Button>
                )}
                <Button type="button" size="sm" onClick={next}>
                  {stepIndex >= STEPS.length - 1 ? "Get started" : "Next"}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
