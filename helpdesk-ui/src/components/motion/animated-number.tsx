"use client"

import * as React from "react"
import { animate, useMotionValue, useTransform, motion } from "framer-motion"

export interface AnimatedNumberProps {
  value: number
  duration?: number
  precision?: number
  prefix?: string
  suffix?: string
  className?: string
}

export function AnimatedNumber({
  value,
  duration = 0.9,
  precision = 0,
  prefix = "",
  suffix = "",
  className,
}: AnimatedNumberProps) {
  const motionValue = useMotionValue(0)
  const display = useTransform(motionValue, (latest) =>
    `${prefix}${latest.toFixed(precision)}${suffix}`,
  )

  React.useEffect(() => {
    const controls = animate(motionValue, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
    })
    return () => controls.stop()
  }, [value, duration, motionValue])

  return <motion.span className={className}>{display}</motion.span>
}
