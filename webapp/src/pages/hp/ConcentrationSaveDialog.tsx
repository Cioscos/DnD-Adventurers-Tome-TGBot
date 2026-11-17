import RollNotes from '@/components/rules/RollNotes'
import { D20Breakdown } from '@/components/RollResultModal'
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { spring } from '@/styles/motion'
import AfterRollOptions from '@/components/rules/AfterRollOptions'
import ResultDialog from '@/components/ui/ResultDialog'
import { useRetouched } from '@/hooks/useRetouched'
import type { ConcentrationSaveResult } from '@/api/client'

interface Props {
  result: ConcentrationSaveResult
  onClose: () => void
  /** Il tiro è ritoccabile con i privilegi usati dopo averlo visto. */
  afterRoll?: { charId: number }
}

export default function ConcentrationSaveDialog({ result: rolled, onClose, afterRoll }: Props) {
  const { t } = useTranslation()
  const [result, retouch] = useRetouched(rolled)
  const { success, dc, total, is_critical, lost_concentration } = result

  // RAW: 20 e 1 naturali non decidono il TS; «Fumble!» è dei tiri per colpire, quindi qui resta solo il critico concorde.
  const showCritical = is_critical && success
  const accent = showCritical ? 'gold' : success ? 'emerald' : 'crimson'
  const pulse = showCritical
  const numberColor = success ? 'text-dnd-emerald-bright' : 'text-dnd-crimson-bright'

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={pulse}
      size="sm"
      title={t('character.spells.conc_save_title', { dc })}
      extraActions={afterRoll && !result.auto_fail && (
        <AfterRollOptions
          charId={afterRoll.charId}
          query={{ roll: 'save', ability: 'constitution' }}
          rollToken={rolled}
          onResult={(to) => to.concentration && retouch(to.concentration)}
        />
      )}
    >
      {showCritical && (
        <p className="text-dnd-gold-bright font-bold font-cinzel uppercase tracking-wider">{t('character.dice.critical_banner')}</p>
      )}

      <m.p
        initial={{ scale: 0.4 }}
        animate={{ scale: 1 }}
        transition={{ ...spring.elastic, delay: 0.1 }}
        className={`text-5xl font-black font-display ${numberColor}`}
      >
        {total}
      </m.p>

      <D20Breakdown roll={result} />

      <RollNotes notes={result.notes} autoFail={result.auto_fail} />
      <p className={`font-bold font-cinzel uppercase tracking-wider ${numberColor}`}>
        {success
          ? t('character.spells.conc_save_success')
          : t('character.spells.conc_save_fail')}
      </p>

      {lost_concentration && (
        <p className="text-xs text-dnd-crimson-bright font-body italic">
          {t('character.spells.conc_lost')}
        </p>
      )}
    </ResultDialog>
  )
}
