import React from 'react'
import { m, AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import { pageTransition } from '@/styles/motion'

/**
 * Wrap the route <Routes> children to animate route transitions.
 * Usage: <PageTransition>{routes}</PageTransition>
 */
export default function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait" initial={false}>
      <m.div
        key={location.pathname}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={pageTransition}
        className="min-h-full"
      >
        {children}
      </m.div>
    </AnimatePresence>
  )
}
