import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { spring } from '@/styles/motion'
import ResultDialog from '@/components/ui/ResultDialog'
import type { HitDiceSpendResult } from '@/api/client'

interface Props {
  result: HitDiceSpendResult
  onClose: () => void
}

export default function HitDiceResultDialog({ result, onClose }: Props) {
  const { t } = useTranslation()

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent="emerald"
      size="sm"
      title={t('character.hp.hit_dice_result')}
    >
      <m.p
        initial={{ scale: 0.5 }}
        animate={{ scale: 1 }}
        transition={{ ...spring.elastic, delay: 0.1 }}
        className="text-6xl font-black font-display text-dnd-emerald-bright"
      >
        +{result.healed}
      </m.p>
      <p className="text-xs text-dnd-text-muted font-mono">
        [{result.rolls.join(', ')}] +{result.con_bonus} (COS)
      </p>
      {(result.song_rolls?.length ?? 0) > 0 && (
        <p className="text-xs text-dnd-text-muted font-mono">
          {t('character.hp.song_of_rest', { die: result.song_die })}: +{result.song_rolls?.reduce((a, b) => a + b, 0)}
        </p>
      )}
      <p className="text-sm font-body">
        {t('character.hp.new_hp')}:{' '}
        <span className="font-bold font-mono text-dnd-gold-bright">
          {result.new_current_hp}
        </span>
      </p>
    </ResultDialog>
  )
}
