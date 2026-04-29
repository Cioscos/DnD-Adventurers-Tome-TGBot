import { useTranslation } from 'react-i18next'
import { GiCheckedShield, GiCrossedSwords, GiWeight } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
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
    <Surface variant="tome" className="@container mt-3 !px-3 !py-3">
      <div className="grid grid-cols-3 @max-[300px]:grid-cols-1 @max-[300px]:divide-x-0 @max-[300px]:divide-y @max-[300px]:gap-2 divide-x divide-dnd-gold/20 text-center">
        <div className="px-2 flex flex-col items-center gap-1">
          <div className="text-2xl font-display font-black text-dnd-gold-bright leading-none">
            {char.ac}
          </div>
          <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.ac.short', { defaultValue: 'AC' })}
          </div>
          <GiCheckedShield size={12} className="text-dnd-gold/60" />
        </div>

        <div className="px-2 flex flex-col items-center gap-1">
          <div className={`text-xl font-mono font-bold leading-none ${damage ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text-faint'}`}>
            {damage ?? '—'}
          </div>
          <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.equipment.slots.main_hand', { defaultValue: 'Weapon' })}
          </div>
          <GiCrossedSwords size={12} className="text-[var(--dnd-crimson-bright)]/60" />
        </div>

        <div className="px-2 flex flex-col items-center gap-1">
          <div className={`text-sm font-mono font-bold leading-none ${overload ? 'text-[var(--dnd-amber)]' : 'text-[var(--dnd-emerald-bright)]'}`}>
            {`${encumbrance.toFixed(1)}/${carryCap}`}
          </div>
          <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.equipment.summary.encumbrance', { defaultValue: 'Carry' })}
          </div>
          <GiWeight size={12} className={overload ? 'text-[var(--dnd-amber)]/60' : 'text-[var(--dnd-emerald-bright)]/60'} />
        </div>
      </div>
    </Surface>
  )
}
