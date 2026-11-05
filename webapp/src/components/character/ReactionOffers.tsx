import { useTranslation } from 'react-i18next'
import type { RollOption } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { useWeaponAttackFlow } from '@/hooks/useWeaponAttackFlow'
import type { CharacterFull } from '@/types'

interface ReactionOffersProps {
  char: CharacterFull
  /** Le reazioni che l'ultimo danno ha aperto (Ritorsione). */
  reactions: RollOption[]
  /** La reazione è partita: il chiamante la toglie dall'elenco. */
  onSpent: (key: string) => void
}

/** La proposta di reazione dopo un danno, con l'attacco in un tocco. Va montato sempre (non solo con reazioni):
 *  il modal dell'attacco vive qui e deve restare anche quando la proposta sparisce. */
export default function ReactionOffers({ char, reactions, onSpent }: ReactionOffersProps) {
  const { t } = useTranslation()
  const weaponFlow = useWeaponAttackFlow(char.id, char)

  /** La reazione è un attacco in mischia: arma impugnata (la principale per prima) o colpo senz'armi, con l'opzione già scelta. */
  const reactWith = (reaction: RollOption) => {
    const weapons = (char.items ?? []).filter((i) => i.item_type === 'weapon' && i.is_equipped)
    const weapon = weapons.find((i) => i.equipment_slot === 'main_hand') ?? weapons[0]
    if (weapon) weaponFlow.attackWeapon(weapon.id, 'normal', [reaction.key])
    else weaponFlow.attackUnarmed('normal', [reaction.key])
    onSpent(reaction.key)
  }

  return (
    <>
      {!char.is_dead && reactions.length > 0 && (
        <Surface variant="elevated">
          <p className="mb-2 text-xs font-cinzel uppercase tracking-wider text-dnd-gold-bright">{t('character.hp.reaction_title')}</p>
          <ul className="flex flex-col gap-2">
            {reactions.map((r) => (
              <li key={r.key} className="flex items-center gap-3">
                <span className="min-w-0 flex-1 break-words text-sm font-body text-dnd-text">{r.label}</span>
                <Button size="sm" variant="primary" className="min-h-11 shrink-0" onClick={() => reactWith(r)}>
                  {t('character.hp.reaction_attack')}
                </Button>
              </li>
            ))}
          </ul>
        </Surface>
      )}
      {weaponFlow.elements}
    </>
  )
}
