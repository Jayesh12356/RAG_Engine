"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { PingDot, type PingState } from "./ping-dot"
import { AnimatedNumber } from "@/components/motion/animated-number"
import { cn } from "@/lib/utils"

export interface StatusTileProps {
  icon: React.ReactNode
  label: string
  provider: string
  state: PingState
  latency: number
  hint?: string
  className?: string
}

export function StatusTile({
  icon,
  label,
  provider,
  state,
  latency,
  hint,
  className,
}: StatusTileProps) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-border bg-card/85 p-5 shadow-card",
        className,
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
          {icon}
        </span>
        <PingDot state={state} />
      </header>
      <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">{label}</p>
      <h3 className="mt-1 text-[18px] font-semibold tracking-tight text-fg">{provider}</h3>
      <div className="mt-3 flex items-baseline gap-1.5 text-fg">
        <AnimatedNumber value={latency} className="font-mono text-3xl font-semibold tracking-tight tabular-nums" />
        <span className="text-xs text-muted-fg">ms</span>
      </div>
      {hint ? <p className="mt-1 text-xs text-muted-fg">{hint}</p> : null}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: "radial-gradient(120% 60% at 50% 0%, hsl(var(--primary) / 0.08), transparent 60%)",
        }}
      />
    </motion.div>
  )
}
