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

  const acTotal = char.ac + (char.ac_breakdown?.homebrew ?? 0)

  const strScore = char.ability_scores.find((s) => s.name.toLowerCase() === 'strength')?.value ?? 10
  const carryCap = strScore * 15
  const overload = encumbrance > carryCap
  const carryFormula = t('character.equipment.carry_formula', {
    str: strScore,
    cap: carryCap,
    defaultValue: 'Capacità = 15 × Forza ({{str}}) = {{cap}} lb',
  })

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
          {acTotal}
        </span>
        <span className="flex items-center gap-1.5 text-[10px] font-cinzel uppercase tracking-[0.25em] text-dnd-gold-dim">
          <GiCheckedShield size={11} aria-hidden="true" />
          {t('character.ac.short', { defaultValue: 'AC' })}
        </span>
      </div>

      {/* Hairline divider — visually separates AC hero from inline meta below. */}
      <div className="w-24 h-px bg-dnd-gold-dim/30" aria-hidden="true" />

      {/* Inline meta: weapon damage + carry — sized up + de-muted so critical info reads */}
      <div className="flex items-center gap-3 text-sm font-cinzel uppercase tracking-[0.18em]">
        <span className="flex items-center gap-2 text-dnd-text">
          <GiCrossedSwords size={14} aria-hidden="true" className="text-[var(--dnd-crimson-bright)]" />
          <span className="font-mono normal-case tracking-normal text-dnd-text font-bold tabular-nums">
            {damage ?? '—'}
          </span>
        </span>

        <span aria-hidden="true" className="text-dnd-gold-dim/60 select-none">◈</span>

        <span
          className="flex items-center gap-2 cursor-help"
          title={carryFormula}
          aria-label={carryFormula}
        >
          <GiWeight
            size={14}
            aria-hidden="true"
            className={overload ? 'text-[var(--dnd-amber)]' : 'text-dnd-text-muted'}
          />
          <span className={`font-mono normal-case tracking-normal font-bold tabular-nums ${overload ? 'text-[var(--dnd-amber)]' : 'text-dnd-text'}`}>
            {`${formatWeight(encumbrance)}/${carryCap}`}
            <span className="text-dnd-text-muted ml-0.5 font-normal">lb</span>
          </span>
        </span>
      </div>
    </section>
  )
}
