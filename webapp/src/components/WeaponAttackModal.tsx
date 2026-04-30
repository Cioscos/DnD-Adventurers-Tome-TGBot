import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import {
  GiPolarStar as Star, GiSkullCrossedBones as Skull,
  GiCrossedSwords as Swords,
} from 'react-icons/gi'
import ResultDialog from './ui/ResultDialog'
import InspirationRerollButton from './InspirationRerollButton'

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
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void | Promise<void>
}

export default function WeaponAttackModal({
  result,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
}: Props) {
  const { t } = useTranslation()
  const {
    weapon_name, to_hit_die, to_hit_bonus, to_hit_total,
    is_critical, is_fumble, damage_dice, damage_rolls, damage_bonus, damage_total,
  } = result

  const bonusStr = (n: number) => n >= 0 ? `+${n}` : `${n}`

  const accent = is_critical ? 'gold' : is_fumble ? 'crimson' : 'emerald'
  const showInspirationButton =
    inspirationAvailable && !wasRerolled && onInspirationReroll != null

  const toHitColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-dnd-crimson-bright'
      : 'text-dnd-text'

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={is_critical || is_fumble}
      size="md"
      title={
        <span className="inline-flex items-center justify-center gap-1.5">
          <Swords size={14} className="text-dnd-gold-bright" />
          {weapon_name}
        </span>
      }
      subtitle={wasRerolled ? t('character.inspiration.reroll_badge') : undefined}
      extraActions={
        showInspirationButton ? (
          <InspirationRerollButton
            available
            pending={isRerolling}
            onClick={onInspirationReroll}
          />
        ) : undefined
      }
    >
      {is_critical && (
        <p className="text-dnd-gold-bright font-bold font-cinzel flex items-center justify-center gap-1.5">
          <Star size={14} fill="currentColor" /> CRITICO!
        </p>
      )}
      {is_fumble && (
        <p className="text-dnd-crimson-bright font-bold font-cinzel flex items-center justify-center gap-1.5">
          <Skull size={14} /> FUMBLE!
        </p>
      )}

      <m.div
        className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <p className="text-[10px] text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
          Per colpire
        </p>
        <p className="text-xs text-dnd-text-muted font-body">
          d20 ({to_hit_die}) {bonusStr(to_hit_bonus)}
        </p>
        <p className={`text-4xl font-black font-display mt-1 ${toHitColor}`}>
          {to_hit_total}
        </p>
      </m.div>

      {!is_fumble && (
        <m.div
          className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3"
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
          <p className="text-4xl font-black font-display mt-1 text-dnd-crimson-bright">
            {damage_total}
          </p>
        </m.div>
      )}
    </ResultDialog>
  )
}
