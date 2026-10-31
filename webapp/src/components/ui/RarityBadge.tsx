import { useTranslation } from 'react-i18next'
import type { Rarity } from '@/lib/itemMagic'

const TONE: Record<Rarity, string> = {
  common: 'bg-dnd-chip-bg text-dnd-text-muted border-dnd-border',
  uncommon: 'bg-dnd-emerald/20 text-dnd-emerald-bright border-dnd-emerald/30',
  rare: 'bg-dnd-info/20 text-dnd-info-text border-dnd-info/30',
  very_rare: 'bg-dnd-arcane-deep/50 text-dnd-arcane-bright border-dnd-arcane-bright/40',
  legendary: 'bg-dnd-gold/15 text-dnd-gold-bright border-dnd-gold/40',
  artifact: 'bg-dnd-crimson/20 text-dnd-crimson-bright border-dnd-crimson/30',
}

export default function RarityBadge({ rarity }: { rarity: Rarity }) {
  const { t } = useTranslation()
  return (
    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-md border ${TONE[rarity]}`}>
      {t(`character.inventory.magic.rarity.${rarity}`)}
    </span>
  )
}
