import { useRetouched } from '@/hooks/useRetouched'
import type { OptionResult, RollOptionsQuery } from '@/api/client'
import AfterRollOptions from '@/components/rules/AfterRollOptions'
import RollNotes from '@/components/rules/RollNotes'
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { GiPolarStar as Star, GiSkullCrossedBones as Skull } from 'react-icons/gi'
import { spring } from '@/styles/motion'
import ResultDialog from './ui/ResultDialog'
import InspirationRerollButton from './InspirationRerollButton'
import type { RollMode } from '@/api/client'

export type RollResult = {
  die: number
  dice?: number[]
  mode?: RollMode
  notes?: string[]
  auto_fail?: boolean
  option_result?: OptionResult
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
}

type Props = {
  result: RollResult
  title: string
  /** Situational note (e.g. "advantage vs. magic"), shown under the breakdown. */
  note?: string
  onClose: () => void
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void | Promise<void>
  /** Il tiro è ritoccabile con i privilegi usati dopo averlo visto. */
  afterRoll?: { charId: number; query: RollOptionsQuery }
  /** Prova di caratteristica pura: un 20 naturale non è un critico (il 20 vale solo per attacchi), niente banner «Critico». */
  noCritical?: boolean
}

export default function RollResultModal({
  result: rolled,
  title,
  note,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
  afterRoll,
  noCritical = false,
}: Props) {
  const { t } = useTranslation()
  const [result, retouch] = useRetouched(rolled)
  const { die, bonus, total, is_fumble } = result
  const is_critical = result.is_critical && !noCritical
  const pair = result.dice && result.dice.length === 2 ? result.dice : null
  // The kept die is the first matching face; the other one is the discarded one (dimmed).
  const keptIdx = pair ? pair.indexOf(die) : -1

  // Neutral rolls get the default (gold) frame; emerald/crimson are reserved
  // for nat-20/nat-1 so the accent stays semantic (Semantic Triad), not
  // decorative on an ordinary result.
  const autoFail = !!result.auto_fail
  const accent = is_critical ? 'gold' : is_fumble || autoFail ? 'crimson' : 'default'
  // Il numero protagonista è il TOTALE (tiro + modificatore): è quello che conta
  // per il giocatore. Il colore semantico (oro nat-20 / cremisi nat-1 / neutro)
  // si applica quindi al totale, non più al solo tiro grezzo.
  const numberColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble || autoFail
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
        showInspirationButton || (afterRoll && !autoFail) ? (
          <div className="space-y-2">
            {afterRoll && !autoFail && (
              <AfterRollOptions
                charId={afterRoll.charId}
                query={afterRoll.query}
                rollToken={rolled}
                onResult={(to) => retouch({ ...to, description: rolled.description })}
              />
            )}
            {showInspirationButton && (
              <InspirationRerollButton
                available
                pending={isRerolling}
                onClick={onInspirationReroll}
              />
            )}
          </div>
        ) : undefined
      }
    >
      {autoFail && (
        <p className="text-dnd-crimson-bright font-bold text-sm font-cinzel uppercase tracking-wider">
          {t('character.roll_notes.auto_fail')}
        </p>
      )}
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
        {pair ? (
          <>
            {result.mode === 'disadvantage' ? t('common.roll_mode.disadvantage') : t('common.roll_mode.advantage')}{' '}
            d20 (
            {pair.map((v, i) => (
              <span key={i} className={i === keptIdx ? 'font-bold text-dnd-text' : 'opacity-40 line-through'}>
                {i > 0 && ', '}{v}
              </span>
            ))}
            ) {bonusStr}
          </>
        ) : (
          <>d20 ({die}) {bonusStr}</>
        )}
      </p>

      <RollNotes notes={result.notes} optionResult={result.option_result} />
      {note && <p className="text-xs text-dnd-text font-body">{note}</p>}

      {result.description && (
        <p className="text-xs text-dnd-text-muted italic font-body">{result.description}</p>
      )}
    </ResultDialog>
  )
}
