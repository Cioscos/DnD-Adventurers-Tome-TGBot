import { m, AnimatePresence } from 'framer-motion'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './ui/Ornament'

export type WeaponAttackResult = {
  weapon_name: string
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  damage_dice: string
  damage_rolls: number[]
  damage_bonus: number
  damage_total: number
}

type Props = {
  result: WeaponAttackResult
  onClose: () => void
}

export default function WeaponAttackModal({ result, onClose }: Props) {
  const {
    weapon_name, to_hit_die, to_hit_bonus, to_hit_total,
    is_critical, is_fumble, damage_dice, damage_rolls, damage_bonus, damage_total,
  } = result

  const bonusStr = (n: number) => n >= 0 ? `+${n}` : `${n}`

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
          className={`relative rounded-3xl p-5 pt-7 w-full max-w-sm space-y-4
                      bg-gradient-parchment surface-parchment border-2 ${borderColor} ${pulseClass}
                      shadow-parchment-2xl`}
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.85, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={spring.elastic}
        >
          <div className="text-dnd-gold-dim">
            <CornerFlourishes />
          </div>

          <div className="text-center">
            <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">⚔️ {weapon_name}</p>
            {is_critical && <p className="text-dnd-gold-bright font-bold font-cinzel">✦ CRITICO!</p>}
            {is_fumble && <p className="text-[var(--dnd-crimson-bright)] font-bold font-cinzel">💀 FUMBLE!</p>}
          </div>

          <m.div
            className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <p className="text-[10px] text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">Per colpire</p>
            <p className="text-xs text-dnd-text-muted font-body">
              d20 ({to_hit_die}) {bonusStr(to_hit_bonus)}
            </p>
            <p className={`text-4xl font-black font-display mt-1
              ${is_critical ? 'text-dnd-gold-bright' : is_fumble ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text'}`}>
              {to_hit_total}
            </p>
          </m.div>

          {!is_fumble && (
            <m.div
              className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3 text-center"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <p className="text-[10px] text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
                Danno{is_critical ? ' (critico)' : ''} — {damage_dice}
              </p>
              <p className="text-xs text-dnd-text-muted font-body font-mono">
                [{damage_rolls.join(', ')}] {bonusStr(damage_bonus)}
              </p>
              <p className="text-4xl font-black font-display mt-1 text-[var(--dnd-crimson-bright)]">{damage_total}</p>
            </m.div>
          )}

          <m.button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold
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
