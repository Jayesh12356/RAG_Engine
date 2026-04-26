"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

export interface MarqueeProps {
  children: React.ReactNode
  speed?: number
  className?: string
  pauseOnHover?: boolean
  fade?: boolean
}

export function Marquee({
  children,
  speed = 28,
  className,
  pauseOnHover = true,
  fade = true,
}: MarqueeProps) {
  return (
    <div
      className={cn(
        "group relative w-full overflow-hidden",
        fade && "[mask-image:linear-gradient(to_right,transparent,white_10%,white_90%,transparent)]",
        className,
      )}
    >
      <motion.div
        className={cn(
          "flex w-max items-center gap-12",
          pauseOnHover && "group-hover:[animation-play-state:paused]",
        )}
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: speed, ease: "linear", repeat: Infinity }}
      >
        <div className="flex shrink-0 items-center gap-12">{children}</div>
        <div className="flex shrink-0 items-center gap-12" aria-hidden>
          {children}
        </div>
      </motion.div>
    </div>
  )
}
