import { m } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { spring } from '@/styles/motion'
import { useReducedMotion } from '@/hooks/useReducedMotion'

interface ExpandChevronProps {
  /** true = pannello aperto: il chevron è ruotato di 180° (punta in su). */
  open: boolean
  size?: number
  className?: string
}

/**
 * Indicatore standard collassato/espanso per disclosure e card espandibili.
 * Il colore si imposta via className (il glifo eredita currentColor).
 */
export default function ExpandChevron({
  open,
  size = 14,
  className = 'text-dnd-text-faint',
}: ExpandChevronProps) {
  const reduceMotion = useReducedMotion()
  return (
    <m.span
      aria-hidden
      className={`inline-flex shrink-0 ${className}`}
      animate={{ rotate: open ? 180 : 0 }}
      transition={reduceMotion ? { duration: 0 } : spring.snappy}
    >
      <ChevronDown size={size} />
    </m.span>
  )
}
