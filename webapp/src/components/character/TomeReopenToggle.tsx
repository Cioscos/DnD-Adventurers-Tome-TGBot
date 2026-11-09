import { useTranslation } from 'react-i18next'
import SwitchToggle from '@/components/ui/SwitchToggle'
import type { CharacterFull } from '@/types'

interface Props { char: CharacterFull; value: boolean; onChange: (next: boolean) => void }

/** Patto del Tomo (Warlock 2024): al riposo il Libro delle Ombre si evoca di nuovo e i suoi trucchetti e rituali si scelgono da capo.
 *  Il server toglie solo gli incantesimi scelti per il Libro e rimette le scelte in coda. */
export default function TomeReopenToggle({ char, value, onChange }: Props) {
  const { t } = useTranslation()
  if (!(char.abilities ?? []).some((a) => a.feature_key === 'warlock.pact_of_the_tome')) return null
  return (
    <div className="text-left" data-testid="tome-reopen">
      <SwitchToggle checked={value} onChange={onChange} label={t('character.quick_actions.rest_reopen_tome')}
        hint={t('character.quick_actions.rest_reopen_tome_hint')} />
    </div>
  )
}
