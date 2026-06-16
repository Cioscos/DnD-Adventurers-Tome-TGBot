import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { GiPolarStar as Star, GiSkullCrossedBones as Skull } from 'react-icons/gi'
import { spring } from '@/styles/motion'
import ResultDialog from './ui/ResultDialog'
import InspirationRerollButton from './InspirationRerollButton'

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
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void | Promise<void>
}

export default function RollResultModal({
  result,
  title,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
}: Props) {
  const { t } = useTranslation()
  const { die, bonus, total, is_critical, is_fumble } = result

  // Neutral rolls get the default (gold) frame; emerald/crimson are reserved
  // for nat-20/nat-1 so the accent stays semantic (Semantic Triad), not
  // decorative on an ordinary result.
  const accent = is_critical ? 'gold' : is_fumble ? 'crimson' : 'default'
  // Il numero protagonista è il TOTALE (tiro + modificatore): è quello che conta
  // per il giocatore. Il colore semantico (oro nat-20 / cremisi nat-1 / neutro)
  // si applica quindi al totale, non più al solo tiro grezzo.
  const numberColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-dnd-crimson-bright'
      : 'text-dnd-text'

  const bonusStr = bonus >= 0 ? `+${bonus}` : `${bonus}`
  const showInspirationButton =
    inspirationAvailable && !wasRerolled && onInspirationReroll != null

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={is_critical || is_fumble}
      size="sm"
      title={title}
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
        <m.p
          className="text-dnd-gold-bright font-bold text-sm font-cinzel uppercase tracking-wider flex items-center justify-center gap-1.5"
          initial={{ scale: 0.5 }}
          animate={{ scale: [0.5, 1.2, 1] }}
          transition={{ duration: 0.5 }}
        >
          <Star size={14} fill="currentColor" /> {t('character.dice.critical_banner')}
        </m.p>
      )}
      {is_fumble && (
        <m.p
          className="text-dnd-crimson-bright font-bold text-sm font-cinzel uppercase tracking-wider flex items-center justify-center gap-1.5"
          initial={{ scale: 0.5 }}
          animate={{ scale: [0.5, 1.2, 1] }}
          transition={{ duration: 0.5 }}
        >
          <Skull size={14} /> {t('character.dice.fumble_banner')}
        </m.p>
      )}

      <m.div
        key={`total-${total}-${wasRerolled}`}
        className={`text-7xl font-black font-display ${numberColor}`}
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ ...spring.elastic, delay: 0.1 }}
      >
        {total}
      </m.div>

      <p key={`breakdown-${die}-${wasRerolled}`} className="text-xs text-dnd-text-muted font-mono">
        d20 ({die}) {bonusStr}
      </p>

      {result.description && (
        <p className="text-xs text-dnd-text-muted italic font-body">{result.description}</p>
      )}
    </ResultDialog>
  )
}
