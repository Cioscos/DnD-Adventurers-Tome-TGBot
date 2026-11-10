import { apiErrorCode } from '@/lib/mutationError'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { useToast } from '@/hooks/useToast'
import type { CharacterFull, Item } from '@/types'

const ERRORS = ['bond_limit', 'invalid_replacement', 'not_a_weapon', 'bond_unavailable', 'not_bonded', 'already_in_hand', 'no_free_hand', 'turn_slot_used', 'incapacitated']

/** Arma Vincolata (Cavaliere Mistico): fino a due armi vincolate col rituale di un'ora, evocate in mano con l'azione bonus.
 *  Il server impone il limite, la mano libera e l'azione bonus; qui il giocatore dichiara il rituale concluso. */
export default function WeaponBondSheet({ char, onClose }: { char: CharacterFull; onClose: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [replacing, setReplacing] = useState<Item | null>(null)
  const weapons = (char.items ?? []).filter((i) => i.item_type === 'weapon')
  const bonded = weapons.filter((i) => !!i.item_metadata?.bonded)
  const inHand = (i: Item) => i.is_equipped && (i.equipment_slot === 'main_hand' || i.equipment_slot === 'off_hand')

  const done = (updated: CharacterFull) => {
    qc.setQueryData(['character', char.id], updated)
    qc.invalidateQueries({ queryKey: ['turn-state', char.id] })
    setReplacing(null)
  }
  // Il server dice perché rifiuta (limite, mano occupata, azione bonus già spesa): si traduce, mai il messaggio tecnico.
  const fail = (err: unknown) => {
    const code = apiErrorCode(err)
    toast.error(t(`character.weapon_bond.errors.${code && ERRORS.includes(code) ? code : 'default'}`))
    qc.invalidateQueries({ queryKey: ['character', char.id] })
  }
  const bond = useMutation({
    mutationFn: ({ item, replaceId }: { item: Item; replaceId?: number }) => api.items.bond(char.id, item.id, replaceId),
    onSuccess: done, onError: fail,
  })
  const breakBond = useMutation({ mutationFn: (item: Item) => api.items.breakBond(char.id, item.id), onSuccess: done, onError: fail })
  const summon = useMutation({
    mutationFn: (item: Item) => api.items.summon(char.id, item.id),
    onSuccess: (updated) => { done(updated); toast.info(t('character.weapon_bond.summoned')) },
    onError: fail,
  })
  const busy = bond.isPending || breakBond.isPending || summon.isPending

  const startBond = (item: Item) => (bonded.length >= 2 ? setReplacing(item) : bond.mutate({ item }))

  return (
    <Sheet open onClose={onClose} title={t('character.weapon_bond.title')} zClassName="z-[60]">
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="text-xs font-body text-dnd-text-muted">{t('character.weapon_bond.hint')}</p>
        {weapons.length === 0 && <p className="text-sm font-body text-dnd-text-muted">{t('character.weapon_bond.empty')}</p>}
        {replacing && (
          <div data-testid="bond-replace" className="flex flex-col gap-2 rounded-xl border border-dnd-gold-dim p-3">
            <p className="text-sm font-body text-dnd-text">{t('character.weapon_bond.replace_prompt', { name: replacing.name })}</p>
            {bonded.map((old) => (
              <Button key={old.id} variant="secondary" disabled={busy} onClick={() => bond.mutate({ item: replacing, replaceId: old.id })}>
                {t('character.weapon_bond.break_for', { name: old.name })}
              </Button>
            ))}
            <Button variant="ghost" onClick={() => setReplacing(null)}>{t('common.cancel')}</Button>
          </div>
        )}
        <ul className="divide-y divide-dnd-border/60">
          {weapons.map((item) => {
            const isBonded = !!item.item_metadata?.bonded
            return (
              <li key={item.id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="min-w-0 flex-1 truncate font-body text-sm text-dnd-text">
                  {item.name}
                  {isBonded && <span className="ml-2 text-xs text-dnd-gold-bright">{t('character.weapon_bond.bonded')}</span>}
                </span>
                {isBonded ? (
                  <>
                    <Button size="sm" variant="primary" disabled={busy || inHand(item)} onClick={() => summon.mutate(item)}>
                      {inHand(item) ? t('character.weapon_bond.in_hand') : t('character.weapon_bond.summon')}
                    </Button>
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => breakBond.mutate(item)}>
                      {t('character.weapon_bond.break')}
                    </Button>
                  </>
                ) : (
                  <Button size="sm" variant="secondary" disabled={busy} onClick={() => startBond(item)}>
                    {t('character.weapon_bond.bond')}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      </div>
    </Sheet>
  )
}
