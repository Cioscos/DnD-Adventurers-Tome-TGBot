import type { Variants, Transition } from 'framer-motion'

/** Durations (ms) */
export const duration = {
  instant: 80,
  fast: 160,
  normal: 260,
  slow: 460,
  emphatic: 720,
} as const

/** Easing curves (cubic-bezier tuples) */
export const ease = {
  out: [0.25, 0.1, 0.25, 1] as const,
  outBack: [0.34, 1.56, 0.64, 1] as const,
  outExpo: [0.16, 1, 0.3, 1] as const,
  inOut: [0.4, 0, 0.2, 1] as const,
  inkSpread: [0.22, 0.61, 0.36, 1] as const,
}

/** Spring presets */
export const spring: Record<string, Transition> = {
  press: { type: 'spring', stiffness: 420, damping: 28, mass: 0.6 },
  drift: { type: 'spring', stiffness: 180, damping: 22, mass: 0.9 },
  snappy: { type: 'spring', stiffness: 320, damping: 26 },
  elastic: { type: 'spring', stiffness: 240, damping: 10, mass: 1 },
  swipe: { type: 'spring', stiffness: 260, damping: 28 },
}

/** Stagger delays (seconds — framer-motion uses seconds) */
export const stagger = {
  list: 0.045,
  listTight: 0.025,
  hero: 0.12,
} as const

/** Reusable variant presets */
export const motionVariants: Record<string, Variants> = {
  fadeUp: {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -8 },
  },
  scaleIn: {
    initial: { opacity: 0, scale: 0.96 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.98 },
  },
  modalSheet: {
    initial: { y: '100%' },
    animate: { y: 0 },
    exit: { y: '100%' },
  },
  flourish: {
    initial: { opacity: 0, scale: 0.8, rotate: -2 },
    animate: { opacity: 1, scale: 1, rotate: 0 },
  },
  slideFromRight: {
    initial: { opacity: 0, x: 24 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -16 },
  },
}

/** Common page-transition transition bundles */
export const pageTransition: Transition = {
  ...spring.drift,
  opacity: { duration: duration.fast / 1000 },
}
