import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { spring } from '@/styles/motion'
import ResultDialog from '@/components/ui/ResultDialog'
import type { ConcentrationSaveResult } from '@/api/client'

interface Props {
  result: ConcentrationSaveResult
  onClose: () => void
}

export default function ConcentrationSaveDialog({ result, onClose }: Props) {
  const { t } = useTranslation()
  const { success, dc, total, die, bonus, is_critical, is_fumble, lost_concentration } = result

  // RAW: 20 e 1 naturali non decidono il TS, quindi il banner compare solo se concorda con l'esito.
  const showCritical = is_critical && success
  const showFumble = is_fumble && !success
  const accent = showCritical ? 'gold' : success ? 'emerald' : 'crimson'
  const pulse = showCritical || showFumble
  const numberColor = success ? 'text-dnd-emerald-bright' : 'text-dnd-crimson-bright'

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={pulse}
      size="sm"
      title={<>🔮 {t('character.spells.conc_save_title', { dc })}</>}
    >
      {showCritical && (
        <p className="text-dnd-gold-bright font-bold font-cinzel uppercase tracking-wider">✦ {t('character.dice.critical_banner')}</p>
      )}
      {showFumble && (
        <p className="text-dnd-crimson-bright font-bold font-cinzel uppercase tracking-wider">💀 {t('character.dice.fumble_banner')}</p>
      )}

      <m.p
        initial={{ scale: 0.4 }}
        animate={{ scale: 1 }}
        transition={{ ...spring.elastic, delay: 0.1 }}
        className={`text-5xl font-black font-display ${numberColor}`}
      >
        {total}
      </m.p>

      <p className="text-xs text-dnd-text-muted font-mono">
        d20 ({die}) {bonus >= 0 ? '+' : ''}{bonus}
      </p>

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
