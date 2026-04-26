"use client"

import { cn } from "@/lib/utils"

export interface RingPulseProps {
  count?: number
  size?: number
  className?: string
}

export function RingPulse({ count = 3, size = 220, className }: RingPulseProps) {
  return (
    <div
      aria-hidden
      className={cn("relative", className)}
      style={{ width: size, height: size }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          className="absolute inset-0 rounded-full border border-primary/40 animate-ring-pulse"
          style={{
            animationDelay: `${i * 0.6}s`,
          }}
        />
      ))}
      <span className="absolute inset-0 rounded-full bg-primary/15 [filter:blur(24px)]" />
    </div>
  )
}
