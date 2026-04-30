import { useTranslation } from 'react-i18next'
import { GiCheckedShield, GiCrossedSwords, GiWeight } from 'react-icons/gi'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

function formatWeight(n: number): string {
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(1).replace(/\.0$/, '')
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

  const carryColor = overload
    ? 'text-[var(--dnd-amber)]'
    : 'text-dnd-text-muted'

  return (
    <section
      aria-label={t('character.equipment.equipment', { defaultValue: 'Equipment' })}
      className="mt-3 flex flex-col items-center gap-3 px-2"
    >
      {/* AC — hero */}
      <div className="flex flex-col items-center gap-1">
        <span
          aria-hidden="true"
          className="font-mono font-black text-dnd-gold-bright leading-none"
          style={{ fontSize: 'clamp(2.25rem, 9vw, 3rem)' }}
        >
          {char.ac}
        </span>
        <span className="flex items-center gap-1.5 text-[10px] font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim">
          <GiCheckedShield size={11} aria-hidden="true" />
          {t('character.ac.short', { defaultValue: 'AC' })}
        </span>
      </div>

      {/* Inline meta: weapon damage + carry */}
      <div className="flex items-center gap-3 text-[11px] font-cinzel uppercase tracking-[0.18em]">
        <span className="flex items-center gap-1.5 text-dnd-text-muted">
          <GiCrossedSwords size={12} aria-hidden="true" className="text-[var(--dnd-crimson-bright)]/70" />
          <span className="font-mono normal-case tracking-normal text-dnd-text">
            {damage ?? '—'}
          </span>
        </span>

        <span aria-hidden="true" className="text-dnd-gold-dim/60 select-none">◈</span>

        <span className="flex items-center gap-1.5 text-dnd-text-muted">
          <GiWeight
            size={12}
            aria-hidden="true"
            className={overload ? 'text-[var(--dnd-amber)]/80' : 'text-dnd-text-faint'}
          />
          <span className={`font-mono normal-case tracking-normal ${carryColor}`}>
            {`${formatWeight(encumbrance)}/${carryCap}`}
            <span className="text-dnd-text-faint ml-0.5">lb</span>
          </span>
        </span>
      </div>
    </section>
  )
}
