"use client"

import * as React from "react"
import { motion, useInView, type HTMLMotionProps } from "framer-motion"
import { fadeUp, stagger as staggerVariants } from "@/lib/motion"

export interface StaggerProps extends Omit<HTMLMotionProps<"div">, "ref"> {
  delayChildren?: number
  staggerChildren?: number
  once?: boolean
  amount?: number | "some" | "all"
}

export function Stagger({
  children,
  delayChildren = 0.05,
  staggerChildren = 0.07,
  once = true,
  amount = 0.2,
  className,
  ...rest
}: StaggerProps) {
  const ref = React.useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once, amount })
  return (
    <motion.div
      ref={ref}
      className={className}
      initial="hidden"
      animate={inView ? "visible" : "hidden"}
      variants={staggerVariants(delayChildren, staggerChildren)}
      {...rest}
    >
      {children}
    </motion.div>
  )
}

export function StaggerItem({
  children,
  className,
  ...rest
}: Omit<HTMLMotionProps<"div">, "ref">) {
  return (
    <motion.div className={className} variants={fadeUp} {...rest}>
      {children}
    </motion.div>
  )
}
