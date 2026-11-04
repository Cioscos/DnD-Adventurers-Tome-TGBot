import RollNotes from '@/components/rules/RollNotes'
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { spring } from '@/styles/motion'
import AfterRollOptions from '@/components/rules/AfterRollOptions'
import ResultDialog from '@/components/ui/ResultDialog'
import { useRetouched } from '@/hooks/useRetouched'
import type { DeathSaveRollResult } from '@/api/client'

interface Props {
  result: DeathSaveRollResult
  onClose: () => void
  /** Il tiro è ritoccabile con i privilegi usati dopo averlo visto. */
  afterRoll?: { charId: number }
}

export default function DeathSaveResultDialog({ result: rolled, onClose, afterRoll }: Props) {
  const { t } = useTranslation()
  const [result, retouch] = useRetouched(rolled)
  const { outcome, die, successes, failures, revived, stable } = result

  const isSuccess = outcome === 'success' || outcome === 'nat20'
  const accent = outcome === 'nat20' ? 'gold' : isSuccess ? 'emerald' : 'crimson'
  const pulse = outcome === 'nat20' || outcome === 'nat1'

  const dieColor = outcome === 'nat20'
    ? 'text-dnd-gold-bright'
    : outcome === 'success'
      ? 'text-dnd-emerald-bright'
      : 'text-dnd-crimson-bright'

  const verdictColor = isSuccess ? 'text-dnd-emerald-bright' : 'text-dnd-crimson-bright'

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={pulse}
      size="sm"
      title={t('character.death_saves.roll_result')}
      extraActions={afterRoll && (
        <AfterRollOptions
          charId={afterRoll.charId}
          query={{ roll: 'death_save' }}
          rollToken={rolled}
          onResult={(to) => to.death && retouch(to.death)}
        />
      )}
    >
      {outcome === 'nat20' && (
        <p className="text-dnd-gold-bright font-bold font-cinzel">
          {t('character.death_saves.nat20')}
        </p>
      )}
      {outcome === 'nat1' && (
        <p className="text-dnd-crimson-bright font-bold font-cinzel">
          {t('character.death_saves.nat1')}
        </p>
      )}

      <m.p
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ ...spring.elastic, delay: 0.1 }}
        className={`text-7xl font-black font-display ${dieColor}`}
      >
        {die}
      </m.p>

      <RollNotes notes={result.notes} />
      <p className={`font-bold font-cinzel uppercase tracking-wider ${verdictColor}`}>
        {isSuccess
          ? t('character.death_saves.success')
          : t('character.death_saves.failure')}
      </p>

      {revived && (
        <p className="text-dnd-gold-bright text-sm font-medium font-body italic">
          {t('character.death_saves.revived')}
        </p>
      )}
      {stable && !revived && (
        <p className="text-dnd-emerald-bright text-sm font-medium font-body italic">
          {t('character.death_saves.stable_3_successes')}
        </p>
      )}
      {failures >= 3 && (
        <p className="text-dnd-crimson-bright text-sm font-medium font-body italic">
          {t('character.death_saves.dead_3_failures')}
        </p>
      )}

      <p className="text-xs text-dnd-text-muted font-mono">
        ✓ {successes}/3 · ✗ {failures}/3
      </p>
    </ResultDialog>
  )
}
