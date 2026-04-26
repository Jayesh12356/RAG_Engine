"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

export interface GlowOrbProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: number
  color?: string
  intensity?: number
}

export function GlowOrb({
  size = 480,
  color = "hsl(var(--primary) / 0.55)",
  intensity = 0.85,
  className,
  style,
  ...rest
}: GlowOrbProps) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute rounded-full animate-orb-drift blur-3xl", className)}
      style={{
        width: size,
        height: size,
        background: `radial-gradient(circle at 50% 50%, ${color} 0%, transparent 70%)`,
        opacity: intensity,
        ...style,
      }}
      {...rest}
    />
  )
}
