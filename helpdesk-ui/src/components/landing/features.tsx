"use client"

import { Brain, Cpu, ShieldCheck } from "lucide-react"
import { Stagger, StaggerItem } from "@/components/motion/stagger"

const FEATURES = [
  {
    icon: Brain,
    title: "Grounded reasoning",
    description:
      "Hybrid retrieval blends dense vectors with sparse BM25 to surface every relevant chunk before the model speaks.",
  },
  {
    icon: ShieldCheck,
    title: "Refusal guardrails",
    description:
      "Pre-gates and PII detection refuse politely when the answer isn't in your docs — no hallucinations sneaking through.",
  },
  {
    icon: Cpu,
    title: "Provider agnostic",
    description:
      "Drop in OpenAI, Anthropic, Cohere or local models. Embeddings stay consistent across failover.",
  },
]

export function Features() {
  return (
    <section id="features" className="relative mx-auto max-w-7xl px-6 py-24">
      <div className="mb-12 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          What makes it different
        </p>
        <h2 className="mt-3 text-4xl font-bold tracking-[-0.025em] text-fg md:text-5xl">
          Built for answers you can trust.
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-[17px] text-muted-fg">
          Three layers of accuracy stacked on top of every retrieval — so users get cited answers,
          not eloquent guesses.
        </p>
      </div>
      <Stagger className="grid gap-5 md:grid-cols-3">
        {FEATURES.map((feat) => {
          const Icon = feat.icon
          return (
            <StaggerItem key={feat.title}>
              <div className="group h-full rounded-2xl border border-border bg-card/70 p-7 shadow-card backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-glow">
                <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary transition-all duration-300 group-hover:scale-110 group-hover:border-primary/50">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-semibold tracking-tight text-fg">{feat.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-fg">{feat.description}</p>
              </div>
            </StaggerItem>
          )
        })}
      </Stagger>
    </section>
  )
}
