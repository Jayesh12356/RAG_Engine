"use client"

import { cn } from "@/lib/utils"

export type PingState = "ok" | "warn" | "error" | "idle"

const COLOR: Record<PingState, string> = {
  ok: "bg-success",
  warn: "bg-warning",
  error: "bg-danger",
  idle: "bg-muted-fg/60",
}

const RING: Record<PingState, string> = {
  ok: "bg-success/40",
  warn: "bg-warning/40",
  error: "bg-danger/40",
  idle: "bg-muted-fg/30",
}

export function PingDot({ state, className }: { state: PingState; className?: string }) {
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5", className)} aria-hidden>
      <span
        className={cn(
          "absolute inline-flex h-full w-full rounded-full opacity-75",
          state !== "idle" && "animate-ping",
          RING[state],
        )}
      />
      <span className={cn("relative inline-flex h-full w-full rounded-full", COLOR[state])} />
    </span>
  )
}
