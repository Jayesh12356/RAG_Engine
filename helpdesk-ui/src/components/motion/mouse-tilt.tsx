"use client"

import * as React from "react"
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion"
import { cn } from "@/lib/utils"

type DivAttrs = Omit<
  React.HTMLAttributes<HTMLDivElement>,
  "onAnimationStart" | "onAnimationEnd" | "onAnimationIteration" | "onDrag" | "onDragEnd" | "onDragStart"
>

export interface MouseTiltProps extends DivAttrs {
  intensity?: number
  glare?: boolean
  children?: React.ReactNode
}

export function MouseTilt({
  intensity = 8,
  glare = true,
  className,
  children,
  ...rest
}: MouseTiltProps) {
  const ref = React.useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 180, damping: 18 })
  const sy = useSpring(y, { stiffness: 180, damping: 18 })

  const rotateX = useTransform(sy, [-0.5, 0.5], [intensity, -intensity])
  const rotateY = useTransform(sx, [-0.5, 0.5], [-intensity, intensity])
  const glareX = useTransform(sx, [-0.5, 0.5], ["20%", "80%"])
  const glareY = useTransform(sy, [-0.5, 0.5], ["20%", "80%"])
  const glareBackground = useTransform(
    [glareX, glareY] as unknown as never,
    ([gx, gy]: [string, string]) =>
      `radial-gradient(circle at ${gx} ${gy}, hsl(var(--primary) / 0.35) 0%, transparent 55%)`,
  )

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    const px = (event.clientX - rect.left) / rect.width - 0.5
    const py = (event.clientY - rect.top) / rect.height - 0.5
    x.set(px)
    y.set(py)
  }

  const handleMouseLeave = () => {
    x.set(0)
    y.set(0)
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ rotateX, rotateY, transformPerspective: 900, transformStyle: "preserve-3d" }}
      className={cn("relative will-change-transform", className)}
      {...rest}
    >
      {children}
      {glare && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] mix-blend-overlay opacity-60"
          style={{ background: glareBackground }}
        />
      )}
    </motion.div>
  )
}
