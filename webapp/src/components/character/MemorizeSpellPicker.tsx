import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { CharacterFull } from '@/types'

const FEATURE = 'wizard.memorize_spell'
const FIELD = 'w-full min-h-[44px] px-3 rounded-xl bg-dnd-surface border border-dnd-border text-sm font-body text-dnd-text'

export interface MemorizeChoice { out: number; into: number }
interface Props { char: CharacterFull; onChange: (next: MemorizeChoice | null) => void }

/** Memorizzare Incantesimo (Mago 2024, 5°) nel foglio del riposo breve: un incantesimo preparato (non sempre preparato) si
 *  scambia con uno del libro. Il server ricontrolla tutto (libro, livello degli slot, preparati). */
export default function MemorizeSpellPicker({ char, onChange }: Props) {
  const { t } = useTranslation()
  const [half, setHalf] = useState({ out: 0, into: 0 })  // finché non ci sono entrambi non è ancora uno scambio
  if (!(char.abilities ?? []).some((a) => a.feature_key === FEATURE)) return null

  const top = Math.max(0, ...(char.spell_slots ?? []).filter((s) => !s.is_pact && s.total > 0).map((s) => s.level))
  const spells = (char.spells ?? []).filter((s) => s.level >= 1)
  const outs = spells.filter((s) => s.is_prepared && !s.always_prepared)
  const ins = spells.filter((s) => s.in_spellbook && !s.is_prepared && s.level <= top)
  if (outs.length === 0 || ins.length === 0) return null

  const set = (key: keyof MemorizeChoice, raw: string) => {
    const next = { ...half, [key]: Number(raw) }
    setHalf(next)
    onChange(next.out && next.into ? next : null)
  }

  return (
    <section data-testid="memorize-spell" className="space-y-2 text-left">
      <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.quick_actions.memorize_spell')}</h3>
      <p className="text-sm font-body text-dnd-text">{t('character.quick_actions.memorize_spell_hint')}</p>
      <select data-testid="memorize-out" value={half.out || ''} className={FIELD} aria-label={t('character.quick_actions.memorize_spell_out')}
        onChange={(e) => set('out', e.target.value)}>
        <option value="">{t('character.quick_actions.memorize_spell_out')}</option>
        {outs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <select data-testid="memorize-into" value={half.into || ''} className={FIELD} aria-label={t('character.quick_actions.memorize_spell_into')}
        onChange={(e) => set('into', e.target.value)}>
        <option value="">{t('character.quick_actions.memorize_spell_into')}</option>
        {ins.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
    </section>
  )
}
