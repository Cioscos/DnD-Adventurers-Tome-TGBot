import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import SwitchToggle from '@/components/ui/SwitchToggle'
import type { CharacterFull } from '@/types'

const CUNNING = 'warlock.magical_cunning'

interface Props { char: CharacterFull; value: number[]; onChange: (next: number[]) => void }

/** Resilienza Celestiale (Warlock 2024, 10\°) a fine riposo: fino a `ally_max` PG della serata ricevono i PF temporanei. L'app la
 *  riconosce da Astuzia Magica, che offre i riceventi solo al Celestiale. Il server ricontrolla serata, numero e valore. */
export default function RestAllyTempPicker({ char, value, onChange }: Props) {
  const { t } = useTranslation()
  const max = (char.abilities ?? []).find((a) => a.feature_key === CUNNING && a.gives_to_ally)?.ally_max ?? 0
  const { data: allies = [] } = useQuery({ queryKey: ['session-allies', char.id], queryFn: () => api.characters.sessionAllies(char.id), enabled: max > 0 })
  if (max < 1 || allies.length === 0) return null
  const toggle = (id: number, on: boolean) => onChange(on ? (value.length < max ? [...value, id] : value) : value.filter((x) => x !== id))
  return (
    <section data-testid="rest-ally-temp" className="space-y-2 text-left">
      <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.quick_actions.rest_ally_temp')}</h3>
      <p className="text-sm font-body text-dnd-text">{t('character.quick_actions.rest_ally_temp_hint', { max })}</p>
      {allies.map((a) => (
        <SwitchToggle key={a.id} checked={value.includes(a.id)} onChange={(on) => toggle(a.id, on)} label={a.name} aria-label={a.name} />
      ))}
    </section>
  )
}
