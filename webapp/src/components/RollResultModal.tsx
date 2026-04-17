import { m, AnimatePresence } from 'framer-motion'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './ui/Ornament'

export type RollResult = {
  die: number
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
}

type Props = {
  result: RollResult
  title: string
  onClose: () => void
}

export default function RollResultModal({ result, title, onClose }: Props) {
  const { die, bonus, total, is_critical, is_fumble } = result

  const borderColor = is_critical
    ? 'border-dnd-gold'
    : is_fumble
      ? 'border-dnd-crimson'
      : 'border-dnd-emerald'

  const pulseClass = is_critical
    ? 'animate-pulse-gold'
    : is_fumble
      ? 'animate-pulse-danger'
      : ''

  const dieColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-[var(--dnd-crimson-bright)]'
      : 'text-dnd-text'

  const bonusStr = bonus >= 0 ? `+${bonus}` : `${bonus}`

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 flex items-center justify-center z-50 p-4"
        style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <m.div
          className={`relative rounded-3xl p-6 pt-8 w-full max-w-xs text-center space-y-3
                      bg-gradient-parchment surface-parchment border-2 ${borderColor} ${pulseClass}
                      shadow-parchment-2xl`}
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.8, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={spring.elastic}
        >
          <div className="text-dnd-gold-dim">
            <CornerFlourishes />
          </div>

          <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">{title}</p>

          {is_critical && (
            <m.p
              className="text-dnd-gold-bright font-bold text-sm font-cinzel uppercase tracking-wider"
              initial={{ scale: 0.5 }}
              animate={{ scale: [0.5, 1.2, 1] }}
              transition={{ duration: 0.5 }}
            >
              ✦ CRITICO!
            </m.p>
          )}
          {is_fumble && (
            <m.p
              className="text-[var(--dnd-crimson-bright)] font-bold text-sm font-cinzel uppercase tracking-wider"
              initial={{ scale: 0.5 }}
              animate={{ scale: [0.5, 1.2, 1] }}
              transition={{ duration: 0.5 }}
            >
              💀 FUMBLE!
            </m.p>
          )}

          <m.div
            className={`text-7xl font-black font-display ${dieColor}`}
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ ...spring.elastic, delay: 0.1 }}
          >
            {die}
          </m.div>

          <p className="text-dnd-text-muted text-sm font-body">
            d20 ({die}) {bonusStr} = <span className="text-dnd-text font-bold text-lg font-mono">{total}</span>
          </p>

          {result.description && (
            <p className="text-xs text-dnd-text-muted italic font-body">{result.description}</p>
          )}

          <m.button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold mt-2
                       min-h-[48px] shadow-engrave font-cinzel uppercase tracking-wider"
            whileTap={{ scale: 0.97 }}
          >
            OK
          </m.button>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
