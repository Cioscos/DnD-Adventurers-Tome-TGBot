import { useTranslation } from 'react-i18next'
import { GiBootPrints } from 'react-icons/gi'
import StatPill from '@/components/ui/StatPill'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

export default function VitalsStrip({ char }: Props) {
  const { t } = useTranslation()

  return (
    <div className="@container flex justify-center">
      <StatPill
        icon={<GiBootPrints size={14} />}
        value={`${char.speed} ft`}
        tone="emerald"
        size="sm"
        iconOnly
        revealOnTap
        aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${char.speed} ft`}
      />
    </div>
  )
}
