import { useTranslation } from 'react-i18next'
import { GiCheckedShield, GiCrossedSwords, GiWeight } from 'react-icons/gi'
import StatPill from '@/components/ui/StatPill'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

export default function EquipmentStatsFooter({ char }: Props) {
  const { t } = useTranslation()

  const mainHand = char.items?.find(
    (i) => i.is_equipped && i.equipment_slot === 'main_hand',
  )
  const damage =
    mainHand?.item_metadata && typeof mainHand.item_metadata === 'object'
      ? (mainHand.item_metadata as { damage_dice?: string }).damage_dice
      : null

  const encumbrance = char.items
    ?.filter((i) => i.is_equipped)
    .reduce((sum, i) => sum + (i.weight || 0) * (i.quantity || 1), 0) ?? 0

  const carryCap = (char.ability_scores.find((s) => s.name.toLowerCase() === 'strength')?.value ?? 10) * 15
  const overload = encumbrance > carryCap

  return (
    <div className="mt-3 flex flex-wrap gap-2 justify-center">
      <StatPill
        icon={<GiCheckedShield size={14} />}
        label={t('character.ac.short', { defaultValue: 'AC' })}
        value={String(char.ac)}
        tone="gold"
        size="sm"
      />
      <StatPill
        icon={<GiCrossedSwords size={14} />}
        label={t('character.equipment.slots.main_hand', { defaultValue: 'Weapon' })}
        value={damage ?? '—'}
        tone="crimson"
        size="sm"
      />
      <StatPill
        icon={<GiWeight size={14} />}
        label={t('character.equipment.summary.encumbrance', { defaultValue: 'Carry' })}
        value={`${encumbrance.toFixed(1)} / ${carryCap}`}
        tone={overload ? 'amber' : 'emerald'}
        size="sm"
      />
    </div>
  )
}
