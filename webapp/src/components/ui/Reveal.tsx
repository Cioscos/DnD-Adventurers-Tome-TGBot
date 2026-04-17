import React from 'react'
import { m } from 'framer-motion'
import { motionVariants, spring, stagger as staggerTokens } from '@/styles/motion'

interface StaggerProps {
  children: React.ReactNode
  delay?: number
  stagger?: number
  className?: string
  /** Cap children count for stagger (over this → collective fade without delay). */
  cap?: number
}

function Stagger({ children, delay = 0.1, stagger = staggerTokens.list, className = '', cap = 8 }: StaggerProps) {
  const items = React.Children.toArray(children)
  const useStagger = items.length <= cap

  return (
    <m.div
      className={className}
      initial="initial"
      animate="animate"
      variants={{
        initial: {},
        animate: useStagger
          ? { transition: { staggerChildren: stagger, delayChildren: delay } }
          : { transition: { duration: 0.2 } },
      }}
    >
      {children}
    </m.div>
  )
}

function Item({
  children,
  className = '',
  variants = motionVariants.fadeUp,
}: {
  children: React.ReactNode
  className?: string
  variants?: typeof motionVariants.fadeUp
}) {
  return (
    <m.div className={className} variants={variants} transition={spring.drift}>
      {children}
    </m.div>
  )
}

const Reveal = { Stagger, Item }
export default Reveal
