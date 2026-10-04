import type { ReactNode } from 'react'
import { motion, useReducedMotion, type Variants } from 'motion/react'

/** Shared motion presets so every screen animates with the same rhythm. */
export const ease = [0.22, 1, 0.36, 1] as const

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease } },
}

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}

interface RevealProps {
  children: ReactNode
  className?: string
  delay?: number
}

/** Fades content up once when it scrolls into view. Respects prefers-reduced-motion. */
export function Reveal({ children, className, delay = 0 }: RevealProps) {
  const reduce = useReducedMotion()
  if (reduce) return <div className={className}>{children}</div>
  return (
    <motion.div
      className={className}
      variants={fadeUp}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: '-60px' }}
      transition={{ delay }}
    >
      {children}
    </motion.div>
  )
}

export { motion }
