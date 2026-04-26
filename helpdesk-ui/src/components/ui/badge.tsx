import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.18em] transition-colors",
  {
    variants: {
      variant: {
        primary: "bg-primary/10 text-primary ring-1 ring-inset ring-primary/25",
        secondary: "bg-muted text-muted-fg",
        success: "bg-success/10 text-success ring-1 ring-inset ring-success/25",
        warning: "bg-warning/10 text-warning ring-1 ring-inset ring-warning/25",
        danger: "bg-danger/10 text-danger ring-1 ring-inset ring-danger/25",
        outline: "border border-border text-fg",
      },
    },
    defaultVariants: { variant: "secondary" },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
