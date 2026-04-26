import * as React from "react"
import { cn } from "@/lib/utils"

export const Kbd = React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(
  ({ className, children, ...props }, ref) => (
    <kbd
      ref={ref}
      className={cn(
        "inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded border border-border bg-muted px-1.5 font-mono text-[11px] font-medium text-muted-fg",
        className,
      )}
      {...props}
    >
      {children}
    </kbd>
  ),
)
Kbd.displayName = "Kbd"
