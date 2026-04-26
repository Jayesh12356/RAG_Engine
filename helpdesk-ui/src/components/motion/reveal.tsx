"use client"

import * as React from "react"
import { motion, useInView, type HTMLMotionProps } from "framer-motion"
import { fadeUp } from "@/lib/motion"

export interface RevealProps extends Omit<HTMLMotionProps<"div">, "ref"> {
  delay?: number
  once?: boolean
  amount?: number | "some" | "all"
  as?: "div" | "section" | "article" | "header" | "footer"
}

export function Reveal({
  children,
  delay = 0,
  once = true,
  amount = 0.2,
  as = "div",
  className,
  ...rest
}: RevealProps) {
  const ref = React.useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once, amount })
  const Comp = motion[as] as typeof motion.div
  return (
    <Comp
      ref={ref}
      className={className}
      initial="hidden"
      animate={inView ? "visible" : "hidden"}
      variants={fadeUp}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay }}
      {...rest}
    >
      {children}
    </Comp>
  )
}
