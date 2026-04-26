import { cn } from "@/lib/utils"

export function TypingDots({ className }: { className?: string }) {
  return (
    <span
      aria-label="Assistant is typing"
      className={cn("dot-pulse inline-flex items-center gap-1 text-muted-fg", className)}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
    </span>
  )
}
