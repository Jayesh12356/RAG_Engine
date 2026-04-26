"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  Brain,
  Cpu,
  FileSearch,
  Lock,
  ShieldCheck,
  Sparkles,
  Telescope,
  Workflow,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface DeepDiveSection {
  id: string
  eyebrow: string
  title: string
  blurb: string
  bullets: { icon: React.ComponentType<{ className?: string }>; label: string; body: string }[]
  visual: React.ReactNode
}

const SECTIONS: DeepDiveSection[] = [
  {
    id: "retrieval",
    eyebrow: "Under the hood — Retrieval",
    title: "Hybrid retrieval that actually understands your corpus",
    blurb:
      "Dense embeddings + sparse BM25 are fused with reciprocal-rank fusion, optionally rewritten via HyDE and multi-query, then reranked with a cross-encoder before the model ever sees a token.",
    bullets: [
      {
        icon: FileSearch,
        label: "Hybrid + RRF",
        body: "Dense semantic search and sparse keyword recall are merged with reciprocal-rank fusion for resilient top-K.",
      },
      {
        icon: Telescope,
        label: "HyDE & multi-query",
        body: "Tough questions get rewritten into hypothetical answers and 3-way paraphrases, then unioned and deduped.",
      },
      {
        icon: Brain,
        label: "Cross-encoder rerank",
        body: "BAAI/bge-reranker-base re-scores the candidate set so only the most defensible passages reach the LLM.",
      },
    ],
    visual: <RetrievalVisual />,
  },
  {
    id: "grounding",
    eyebrow: "Under the hood — Grounding",
    title: "Every answer is verified, cited, and tunable",
    blurb:
      "Span-level citations link each sentence to the exact passage that supports it. A groundedness verifier scores each answer and the engine refuses if support drops below your threshold.",
    bullets: [
      {
        icon: ShieldCheck,
        label: "Span-level citations",
        body: "Click a marker and a source viewer slides in, highlighting the exact span — no hand-waving.",
      },
      {
        icon: Sparkles,
        label: "Confidence + refusal",
        body: "A calibrated confidence score is shown on every reply. Answers below your floor refuse politely instead of hallucinating.",
      },
      {
        icon: Workflow,
        label: "Eval harness",
        body: "Ship with a golden YAML and a one-command eval runner so you can prove uplift before every release.",
      },
    ],
    visual: <GroundingVisual />,
  },
  {
    id: "ops",
    eyebrow: "Under the hood — Ops & security",
    title: "Production-grade operations from day one",
    blurb:
      "OpenTelemetry tracing on every stage, structured logs, per-cookie config overrides, slowapi rate limiting, optional PII redaction at ingest, and webhooks for ingestion + query lifecycle events.",
    bullets: [
      {
        icon: Cpu,
        label: "Observability",
        body: "Latency histograms, refusal rate, mean confidence, and per-question cost — surfaced in /app/status and /metrics.",
      },
      {
        icon: Lock,
        label: "Security",
        body: "PII redaction before embedding, per-IP / per-cookie rate limits, and clear audit trails on every mutation.",
      },
      {
        icon: Workflow,
        label: "Automation",
        body: "Webhooks fire on ingest + query events, and an admin CLI handles ingest / query / eval / export-corpus / clear-cache.",
      },
    ],
    visual: <OpsVisual />,
  },
]

export function DeepDive() {
  return (
    <section
      id="deep-dive"
      aria-labelledby="deep-dive-heading"
      className="relative border-t border-border bg-bg"
    >
      <div className="mx-auto w-full max-w-6xl px-6 py-20 lg:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-primary/80">
            Deep dive
          </span>
          <h2
            id="deep-dive-heading"
            className="mt-3 text-balance text-3xl font-semibold tracking-[-0.02em] text-fg sm:text-4xl"
          >
            Premium retrieval, grounded answers, production-grade ops
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted-fg">
            Three stages, each tunable per request. Click into any section to see how the engine
            keeps your answers honest, fast, and observable.
          </p>
        </div>

        <div className="mt-16 space-y-24">
          {SECTIONS.map((section, idx) => (
            <article
              key={section.id}
              id={section.id}
              className={cn(
                "grid gap-10 lg:grid-cols-2 lg:items-center",
                idx % 2 === 1 && "lg:[&>*:first-child]:order-2",
              )}
            >
              <motion.div
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              >
                <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-primary/80">
                  {section.eyebrow}
                </span>
                <h3 className="mt-3 text-2xl font-semibold tracking-[-0.02em] text-fg sm:text-3xl">
                  {section.title}
                </h3>
                <p className="mt-3 text-[15px] leading-relaxed text-muted-fg">{section.blurb}</p>
                <ul className="mt-6 space-y-4">
                  {section.bullets.map((b) => (
                    <li key={b.label} className="flex gap-3">
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-border bg-card text-primary shadow-card">
                        <b.icon className="h-4 w-4" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-fg">{b.label}</p>
                        <p className="mt-1 text-sm leading-relaxed text-muted-fg">{b.body}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, scale: 0.97 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                className="rounded-2xl border border-border bg-card/70 p-4 shadow-card"
              >
                {section.visual}
              </motion.div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function RetrievalVisual() {
  const stages = [
    { label: "Question", color: "from-primary to-accent" },
    { label: "HyDE / paraphrases", color: "from-accent to-primary" },
    { label: "Hybrid (dense + BM25)", color: "from-primary/80 to-accent/80" },
    { label: "RRF fusion", color: "from-accent/80 to-primary/80" },
    { label: "Cross-encoder rerank", color: "from-primary to-accent" },
    { label: "Top-K passages", color: "from-success to-success/70" },
  ]
  return (
    <div className="space-y-3">
      {stages.map((s, i) => (
        <div key={s.label} className="flex items-center gap-3">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md border border-border bg-bg text-[11px] font-semibold text-muted-fg">
            {i + 1}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full bg-gradient-to-r", s.color)}
              style={{ width: `${30 + i * 12}%` }}
            />
          </div>
          <span className="w-44 shrink-0 text-xs font-medium text-fg">{s.label}</span>
        </div>
      ))}
    </div>
  )
}

function GroundingVisual() {
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border bg-bg p-3 text-sm leading-relaxed text-fg">
        <p>
          The 2023 climate report attributes <mark className="rounded bg-primary/20 px-0.5 text-primary">42% of emissions</mark>{" "}
          to industrial activity
          <sup className="ml-0.5 inline-flex items-center justify-center rounded bg-primary/15 px-1 text-[10px] font-semibold text-primary">
            1
          </sup>
          , while transportation accounts for{" "}
          <mark className="rounded bg-accent/20 px-0.5 text-accent">29%</mark>
          <sup className="ml-0.5 inline-flex items-center justify-center rounded bg-accent/15 px-1 text-[10px] font-semibold text-accent">
            2
          </sup>
          .
        </p>
      </div>
      <div className="grid gap-2 text-xs text-muted-fg">
        <div className="flex items-center justify-between rounded-md border border-border bg-bg px-3 py-2">
          <span className="font-medium text-fg">Confidence</span>
          <span className="font-mono text-success">0.92</span>
        </div>
        <div className="flex items-center justify-between rounded-md border border-border bg-bg px-3 py-2">
          <span className="font-medium text-fg">Groundedness</span>
          <span className="font-mono text-success">0.96</span>
        </div>
        <div className="flex items-center justify-between rounded-md border border-border bg-bg px-3 py-2">
          <span className="font-medium text-fg">Refusal threshold</span>
          <span className="font-mono text-muted-fg">0.55</span>
        </div>
      </div>
    </div>
  )
}

function OpsVisual() {
  const ticks = [62, 58, 64, 61, 59, 67, 70, 65, 60, 58, 63, 61]
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-1.5">
        {ticks.map((t, i) => (
          <div
            key={i}
            className="w-3 rounded-sm bg-gradient-to-t from-primary/30 to-primary"
            style={{ height: `${t}px` }}
          />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-md border border-border bg-bg px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-fg">p50</div>
          <div className="mt-1 font-mono text-sm text-fg">412 ms</div>
        </div>
        <div className="rounded-md border border-border bg-bg px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-fg">p95</div>
          <div className="mt-1 font-mono text-sm text-fg">1.18 s</div>
        </div>
        <div className="rounded-md border border-border bg-bg px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-fg">refusal</div>
          <div className="mt-1 font-mono text-sm text-fg">2.1 %</div>
        </div>
      </div>
    </div>
  )
}
