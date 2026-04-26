import * as React from "react"
import { cn } from "@/lib/utils"

export interface WordmarkProps {
  className?: string
  variant?: "compact" | "full"
}

export function Wordmark({ className, variant = "full" }: WordmarkProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 font-semibold tracking-[-0.01em] text-fg",
        variant === "compact" ? "text-base" : "text-xl",
        className,
      )}
    >
      <span className="relative inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md [background-image:var(--grad-primary)] shadow-glow">
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
        >
          <path
            d="M7 1l1.6 4.4L13 7l-4.4 1.6L7 13 5.4 8.6 1 7l4.4-1.6L7 1z"
            fill="hsl(var(--primary-fg))"
          />
        </svg>
      </span>
      {variant === "full" && (
        <span className="leading-none tracking-tight">RAG Engine</span>
      )}
    </span>
  )
}
