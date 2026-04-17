import { useReducedMotion as useFramerReducedMotion } from 'framer-motion'

/**
 * Returns true when the user has requested reduced motion (OS setting).
 * Thin re-export of framer-motion's hook for codebase consistency.
 */
export function useReducedMotion(): boolean {
  return useFramerReducedMotion() ?? false
}
