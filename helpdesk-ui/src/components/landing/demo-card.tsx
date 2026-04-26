"use client"

import { motion } from "framer-motion"
import { CheckCircle2, FileText, Sparkles } from "lucide-react"
import { MouseTilt } from "@/components/motion/mouse-tilt"
import { Badge } from "@/components/ui/badge"

export function DemoCard() {
  return (
    <MouseTilt intensity={6} className="mx-auto w-full max-w-4xl">
      <div className="relative rounded-2xl border border-border bg-card/80 p-1.5 shadow-glow backdrop-blur-md">
        <div className="rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-danger/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-warning/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-success/70" />
            </div>
            <span className="font-mono text-[11px] text-muted-fg">app.rag-engine.dev/chat</span>
            <span className="w-12" />
          </div>

          <div className="grid gap-0 md:grid-cols-[200px_1fr]">
            {/* mini sidebar */}
            <div className="hidden flex-col gap-2 border-r border-border bg-muted/40 p-3 text-[12px] md:flex">
              <span className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">Sessions</span>
              {["Q3 fiscal report", "Onboarding policies", "Vendor SLA review"].map((s, i) => (
                <div
                  key={s}
                  className={`rounded px-2 py-1.5 ${i === 0 ? "bg-card text-fg shadow-card" : "text-muted-fg hover:text-fg"}`}
                >
                  {s}
                </div>
              ))}
            </div>

            {/* conversation */}
            <div className="flex flex-col gap-4 p-5">
              <div className="flex items-start gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-muted text-[11px] font-semibold text-fg">
                  JD
                </span>
                <div className="rounded-2xl rounded-tl-sm bg-muted px-4 py-2.5 text-sm text-fg">
                  What were our Q3 revenue drivers?
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-[11px] font-semibold text-primary-fg [background-image:var(--grad-primary)]">
                  R
                </span>
                <div className="flex-1 space-y-2.5 rounded-2xl rounded-tl-sm border border-border bg-bg p-4 text-sm leading-relaxed shadow-card">
                  <p className="text-fg">
                    Q3 revenue grew <strong className="text-primary">+22% YoY</strong>, driven primarily
                    by the launch of <em>Atlas Tier</em> and a 14% lift in retention from the new
                    onboarding flow.
                  </p>
                  <div className="flex flex-wrap items-center gap-2 pt-2">
                    <Badge variant="primary">
                      <Sparkles className="h-3 w-3" />
                      94% confidence
                    </Badge>
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-fg">
                      <FileText className="h-3 w-3" />
                      Q3-Earnings.pdf • p.4
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-fg">
                      <FileText className="h-3 w-3" />
                      Retention-Memo.pdf • p.2
                    </span>
                  </div>
                </div>
              </div>

              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.4, duration: 0.4 }}
                className="self-end inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-medium text-success ring-1 ring-inset ring-success/25"
              >
                <CheckCircle2 className="h-3 w-3" />
                Sources verified
              </motion.div>
            </div>
          </div>
        </div>
      </div>
    </MouseTilt>
  )
}
