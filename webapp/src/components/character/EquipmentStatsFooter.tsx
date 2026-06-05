import { useTranslation } from 'react-i18next'
import { GiBootPrints, GiCheckedShield, GiCrossedSwords, GiWeight } from 'react-icons/gi'
import type { CharacterFull } from '@/types'
import { useUnitSettings, formatLength, formatWeight, formatWeightValue, weightUnitLabel } from '@/store/unitSettings'

interface Props {
  char: CharacterFull
}

export default function EquipmentStatsFooter({ char }: Props) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)

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

  // Carry capacity is canonical lb on the character; the local STR×15 recompute
  // was removed so a manual override (char.carry_capacity_override) is honored here too.
  const carryCap = char.carry_capacity
  const overload = encumbrance > carryCap

  const speedTotal = (char.speed ?? 30) + (char.speed_homebrew_modifier ?? 0)

  const strScore = char.ability_scores.find((s) => s.name.toLowerCase() === 'strength')?.value ?? 10
  const carryFormula = char.carry_capacity_override
    ? t('character.equipment.carry_override_tooltip', {
        cap: formatWeight(carryCap, system),
        defaultValue: 'Carry capacity (manual override): {{cap}}',
      })
    : t('character.equipment.carry_formula', {
        str: strScore,
        factor: system === 'metric' ? '7.5' : '15',
        cap: formatWeight(carryCap, system),
        defaultValue: 'Carry capacity = {{factor}} × Strength ({{str}}) = {{cap}}',
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
      <div className="flex flex-wrap items-center justify-center gap-3 text-sm font-cinzel uppercase tracking-[0.18em]">
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
            {`${formatWeightValue(encumbrance, system)}/${formatWeightValue(carryCap, system)}`}
            <span className="text-dnd-text-muted ml-0.5 font-normal">{weightUnitLabel(system)}</span>
          </span>
        </span>

        <span aria-hidden="true" className="text-dnd-gold-dim/60 select-none">◈</span>

        <span
          className="flex items-center gap-2 text-dnd-text"
          title={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${formatLength(speedTotal, system)}`}
        >
          <GiBootPrints size={14} aria-hidden="true" className="text-[var(--dnd-emerald-bright)]" />
          <span className="font-mono normal-case tracking-normal text-dnd-text font-bold tabular-nums">
            {formatLength(speedTotal, system)}
          </span>
        </span>
      </div>
    </section>
  )
}
