"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, PlayCircle, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlowOrb } from "@/components/motion/glow-orb"
import { DemoCard } from "@/components/landing/demo-card"
import { ease } from "@/lib/motion"

export function Hero() {
  return (
    <section className="relative isolate overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <GlowOrb
          size={760}
          color="hsl(var(--primary) / 0.45)"
          className="left-1/2 top-[-220px] -translate-x-1/2"
          intensity={0.95}
        />
        <GlowOrb
          size={520}
          color="hsl(var(--accent) / 0.35)"
          className="right-[-180px] top-[120px]"
          intensity={0.65}
        />
        <GlowOrb
          size={420}
          color="hsl(var(--primary) / 0.25)"
          className="left-[-180px] bottom-[40px]"
          intensity={0.55}
        />
        {/* subtle grid */}
        <div
          aria-hidden
          className="absolute inset-0 opacity-[0.18] [mask-image:radial-gradient(ellipse_at_center,white,transparent_70%)]"
          style={{
            backgroundImage:
              "linear-gradient(hsl(var(--border)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--border)) 1px, transparent 1px)",
            backgroundSize: "44px 44px",
          }}
        />
      </div>

      <div className="mx-auto flex max-w-7xl flex-col items-center px-6 pb-12 pt-20 text-center md:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease }}
          className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-fg backdrop-blur"
        >
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          New • Cited answers across every document type
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease, delay: 0.05 }}
          className="mt-6 max-w-4xl text-5xl font-bold leading-[1.04] tracking-[-0.03em] text-fg md:text-7xl"
        >
          Ask anything.{" "}
          <span className="text-shimmer">Across every document.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease, delay: 0.12 }}
          className="mt-5 max-w-2xl text-balance text-[17px] leading-relaxed text-muted-fg md:text-[19px]"
        >
          RAG Engine turns PDFs, Word, Excel/CSV, PowerPoint, text, Markdown, HTML, JSON or images
          into a grounded knowledge surface — with cited answers, confidence scores and refusal
          guardrails out of the box.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease, delay: 0.2 }}
          className="mt-8 flex flex-col gap-3 sm:flex-row"
        >
          <Button asChild size="xl" className="px-7">
            <Link href="/sign-up">
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="secondary" size="xl" className="px-6">
            <a href="#demo-card">
              <PlayCircle className="h-4 w-4" />
              Watch demo
            </a>
          </Button>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, ease, delay: 0.4 }}
          className="mt-5 text-xs text-muted-fg"
        >
          No credit card • Local demo workspace • Works with OpenAI, Anthropic, Cohere
        </motion.p>

        <motion.div
          id="demo-card"
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.9, ease, delay: 0.32 }}
          className="mt-16 w-full"
        >
          <DemoCard />
        </motion.div>
      </div>
    </section>
  )
}
