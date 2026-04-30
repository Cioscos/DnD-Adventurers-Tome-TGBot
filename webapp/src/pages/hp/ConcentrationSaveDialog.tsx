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

  const accent = is_critical ? 'gold' : success ? 'emerald' : 'crimson'
  const pulse = is_critical || is_fumble
  const numberColor = success ? 'text-dnd-emerald-bright' : 'text-dnd-crimson-bright'

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent={accent}
      pulse={pulse}
      size="sm"
      title={<>🔮 {t('character.spells.concentration')} — DC {dc}</>}
    >
      {is_critical && (
        <p className="text-dnd-gold-bright font-bold font-cinzel">✦ CRITICO!</p>
      )}
      {is_fumble && (
        <p className="text-dnd-crimson-bright font-bold font-cinzel">💀 FUMBLE!</p>
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
        <p className="text-[10px] text-dnd-crimson-bright font-body italic">
          {t('character.spells.conc_lost')}
        </p>
      )}
    </ResultDialog>
  )
}
