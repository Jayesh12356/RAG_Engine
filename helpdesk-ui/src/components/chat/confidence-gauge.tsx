"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"

export interface ConfidenceGaugeProps {
  value: number // 0..1
  label?: string
  size?: number
  strokeWidth?: number
  className?: string
  refused?: boolean
  costUsd?: number
  latencyMs?: number
  numSources?: number
}

export function ConfidenceGauge({
  value,
  label,
  size = 88,
  strokeWidth = 8,
  className,
  refused = false,
  costUsd,
  latencyMs,
  numSources,
}: ConfidenceGaugeProps) {
  const [popoverOpen, setPopoverOpen] = React.useState(false)
  const closeTimer = React.useRef<number | null>(null)
  const open = () => {
    if (closeTimer.current) {
      window.clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
    setPopoverOpen(true)
  }
  const closeSoon = () => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current)
    closeTimer.current = window.setTimeout(() => setPopoverOpen(false), 150)
  }
  const clamped = Math.max(0, Math.min(1, value))
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - clamped)
  const pct = Math.round(clamped * 100)

  const tone = refused
    ? "danger"
    : clamped >= 0.7
      ? "primary"
      : clamped >= 0.4
        ? "warning"
        : "danger"

  const stroke =
    tone === "primary"
      ? "url(#cg-gradient)"
      : tone === "warning"
        ? "hsl(var(--warning))"
        : "hsl(var(--danger))"

  const labelText = label ?? (refused ? "Refused" : tone === "primary" ? "High" : tone === "warning" ? "Moderate" : "Low")

  const hasDetails =
    typeof costUsd === "number" || typeof latencyMs === "number" || typeof numSources === "number"

  return (
    <div
      className={cn("relative inline-flex flex-col items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={`Confidence ${pct}% — ${labelText}`}
      onMouseEnter={hasDetails ? open : undefined}
      onMouseLeave={hasDetails ? closeSoon : undefined}
      onFocus={hasDetails ? open : undefined}
      onBlur={hasDetails ? closeSoon : undefined}
      tabIndex={hasDetails ? 0 : -1}
    >
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id="cg-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="hsl(var(--primary))" />
            <stop offset="100%" stopColor="hsl(var(--accent))" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="hsl(var(--border))"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          fill="transparent"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-base font-semibold tabular-nums text-fg">{pct}%</span>
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
          {labelText}
        </span>
      </div>
      <AnimatePresence>
        {popoverOpen && hasDetails && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.14 }}
            className="pointer-events-none absolute left-1/2 top-full z-30 mt-2 w-56 -translate-x-1/2 rounded-md border border-border bg-card/95 p-3 text-left text-xs text-muted-fg shadow-card backdrop-blur"
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-fg">
              Answer telemetry
            </p>
            <ul className="mt-2 space-y-1">
              {typeof costUsd === "number" && (
                <li className="flex justify-between gap-3">
                  <span>Estimated cost</span>
                  <span className="font-mono text-fg">${costUsd.toFixed(4)}</span>
                </li>
              )}
              {typeof latencyMs === "number" && latencyMs > 0 && (
                <li className="flex justify-between gap-3">
                  <span>End-to-end latency</span>
                  <span className="font-mono text-fg">{Math.round(latencyMs)} ms</span>
                </li>
              )}
              {typeof numSources === "number" && (
                <li className="flex justify-between gap-3">
                  <span>Sources cited</span>
                  <span className="font-mono text-fg">{numSources}</span>
                </li>
              )}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function ConfidencePill({
  value,
  refused,
  className,
}: {
  value: number
  refused?: boolean
  className?: string
}) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const tone = refused ? "danger" : value >= 0.7 ? "primary" : value >= 0.4 ? "warning" : "danger"
  const palette: Record<string, string> = {
    primary: "bg-primary/10 text-primary ring-primary/25",
    warning: "bg-warning/10 text-warning ring-warning/30",
    danger: "bg-danger/10 text-danger ring-danger/30",
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        palette[tone],
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {refused ? "Refused" : `${pct}% confident`}
    </span>
  )
}
