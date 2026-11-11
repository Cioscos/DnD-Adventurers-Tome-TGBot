import { useTranslation } from 'react-i18next'
import ChipSelect from '@/components/ui/ChipSelect'
import type { CharacterFull } from '@/types'

interface Props { char: CharacterFull; value: string; onChange: (next: string) => void }

/** Resilienza Immonda (Warlock Immondo 10): finendo il riposo, breve o lungo, si sceglie il tipo di danno a cui si resiste.
 *  I tipi ammessi li dà il server (`rest_damage_choices`); senza scelta resta la resistenza di prima. */
export default function RestResistancePicker({ char, value, onChange }: Props) {
  const { t } = useTranslation()
  const types = (char.abilities ?? []).find((a) => a.rest_damage_choices?.length)?.rest_damage_choices
  if (!types) return null
  const current = (char.active_states ?? []).find((s) => s.key === 'fiendish_resilience')?.data?.damage_type as string | undefined
  const name = (slug: string) => t(`character.inventory.damage_types.dmg_${slug}`)
  return (
    <section data-testid="rest-resistance" className="space-y-2 text-left">
      <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.quick_actions.rest_resistance')}</h3>
      <p className="text-sm font-body text-dnd-text">
        {current ? t('character.quick_actions.rest_resistance_current', { type: name(current) }) : t('character.quick_actions.rest_resistance_none')}
      </p>
      <ChipSelect options={types.map((slug) => ({ value: slug, label: name(slug) }))} value={value}
        onChange={(next) => onChange(next === value ? '' : next)} columns={3} />
    </section>
  )
}
