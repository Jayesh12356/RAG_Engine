"use client"

import { Quote } from "lucide-react"
import { Reveal } from "@/components/motion/reveal"

export function Testimonial() {
  return (
    <section id="testimonial" className="relative mx-auto max-w-7xl px-6 py-24">
      <Reveal>
        <div className="relative mx-auto max-w-3xl rounded-2xl border border-border bg-card/70 p-10 text-center shadow-card backdrop-blur-md md:p-14">
          <Quote className="mx-auto mb-6 h-9 w-9 text-primary" aria-hidden />
          <p className="text-2xl font-medium leading-snug tracking-[-0.01em] text-fg md:text-[26px]">
            “We replaced three different internal search tools with RAG Engine. Confidence scores
            ended an entire category of support tickets — people now <em className="not-italic gradient-text">trust</em>{" "}
            the answer.”
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-full text-sm font-semibold text-primary-fg [background-image:var(--grad-primary)]">
              JK
            </span>
            <div className="text-left">
              <p className="text-sm font-semibold text-fg">Jayesh Koli</p>
              <p className="text-xs text-muted-fg">AI Engineer</p>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  )
}
