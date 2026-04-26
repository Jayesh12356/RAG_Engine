"use client"

import { Marquee } from "@/components/motion/marquee"

const PROVIDERS = [
  "OpenAI",
  "Anthropic",
  "Cohere",
  "Voyage",
  "Qdrant",
  "Postgres",
  "Mistral",
  "Hugging Face",
  "Groq",
  "Together",
]

export function ProvidersMarquee() {
  return (
    <section id="providers" className="border-y border-border bg-card/40 py-10">
      <div className="mx-auto mb-6 flex max-w-7xl items-center justify-between gap-4 px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-fg">
          Plays nicely with the model garden
        </p>
        <span className="hidden text-xs text-muted-fg sm:inline">
          Swap providers without re-indexing
        </span>
      </div>
      <Marquee speed={36}>
        {PROVIDERS.map((p) => (
          <span
            key={p}
            className="text-2xl font-semibold tracking-[-0.01em] text-muted-fg/80 transition-colors hover:text-fg"
          >
            {p}
          </span>
        ))}
      </Marquee>
    </section>
  )
}
