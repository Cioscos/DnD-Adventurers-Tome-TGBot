import { useTranslation } from 'react-i18next'
import { GiBootPrints } from 'react-icons/gi'
import StatPill from '@/components/ui/StatPill'
import { useUnitSettings, formatLength } from '@/store/unitSettings'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

export default function VitalsStrip({ char }: Props) {
  const { t } = useTranslation()
  const unitSystem = useUnitSettings((s) => s.system)
  const speedLabel = formatLength(char.speed ?? 30, unitSystem)

  return (
    <div className="@container flex justify-center">
      <StatPill
        icon={<GiBootPrints size={14} />}
        value={speedLabel}
        tone="emerald"
        size="sm"
        iconOnly
        revealOnTap
        expandHitArea
        aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${speedLabel}`}
      />
    </div>
  )
}
