"use client"

import { motion } from "framer-motion"
import { ArrowRight, FileText, Layers, Sparkles } from "lucide-react"
import { GlowOrb } from "@/components/motion/glow-orb"
import { cn } from "@/lib/utils"

const SUGGESTIONS = [
  { icon: FileText, text: "Summarize the key risks in the latest report." },
  { icon: Layers,   text: "Compare onboarding policies across regions." },
  { icon: Sparkles, text: "Who owns the customer-success roadmap for Q3?" },
]

export function ChatEmptyState({
  onPick,
  className,
}: {
  onPick: (text: string) => void
  className?: string
}) {
  return (
    <div className={cn("relative flex h-full flex-col items-center justify-center px-6 py-12 text-center", className)}>
      <GlowOrb
        size={420}
        color="hsl(var(--primary) / 0.3)"
        className="-translate-x-1/2 left-1/2 top-1/2 -translate-y-1/2"
        intensity={0.55}
      />
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative max-w-xl"
      >
        <div className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-card shadow-glow">
          <Sparkles className="h-5 w-5 text-primary" />
        </div>
        <h2 className="text-3xl font-bold tracking-[-0.025em] text-fg md:text-4xl">
          What can I help you uncover?
        </h2>
        <p className="mt-3 text-sm text-muted-fg">
          Ask grounded questions across every document in your workspace. Drag a PDF into the chat
          to ingest it on the fly.
        </p>

        <div className="mt-7 grid gap-2.5">
          {SUGGESTIONS.map((s, i) => {
            const Icon = s.icon
            return (
              <motion.button
                key={s.text}
                type="button"
                onClick={() => onPick(s.text)}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.06, duration: 0.4 }}
                className="group flex w-full items-center gap-3 rounded-md border border-border bg-card/70 px-4 py-3 text-left text-sm text-fg shadow-card transition-all hover:-translate-y-[1px] hover:border-primary/40 hover:shadow-glow"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-primary transition-colors group-hover:bg-primary/10">
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="flex-1">{s.text}</span>
                <ArrowRight className="h-3.5 w-3.5 text-muted-fg opacity-0 transition-opacity group-hover:opacity-100" />
              </motion.button>
            )
          })}
        </div>
      </motion.div>
    </div>
  )
}
