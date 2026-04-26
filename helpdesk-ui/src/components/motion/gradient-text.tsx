import * as React from "react"
import { cn } from "@/lib/utils"

export const GradientText = React.forwardRef<
  HTMLSpanElement,
  React.HTMLAttributes<HTMLSpanElement> & { shimmer?: boolean }
>(({ className, shimmer = false, ...props }, ref) => (
  <span
    ref={ref}
    className={cn(
      shimmer ? "text-shimmer" : "gradient-text",
      "bg-clip-text",
      className,
    )}
    {...props}
  />
))
GradientText.displayName = "GradientText"
