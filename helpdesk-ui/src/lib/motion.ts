import type { Transition, Variants } from "framer-motion"

export const ease = [0.22, 1, 0.36, 1] as const
export const easeIn = [0.4, 0, 1, 1] as const
export const easeOut = [0, 0, 0.2, 1] as const
export const spring: Transition = { type: "spring", stiffness: 280, damping: 28, mass: 0.8 }

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease } },
}

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4, ease } },
}

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.45, ease } },
}

export const stagger = (delayChildren = 0.05, staggerChildren = 0.06): Variants => ({
  hidden: {},
  visible: {
    transition: { delayChildren, staggerChildren },
  },
})

export const hoverLift = {
  initial: { y: 0 },
  whileHover: { y: -3, transition: { duration: 0.25, ease } },
  whileTap: { y: -1, transition: { duration: 0.1 } },
}

export const messageVariants: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease } },
}

export const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2, ease: easeIn } },
}
