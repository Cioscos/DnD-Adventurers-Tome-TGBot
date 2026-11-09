import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { resolveItemCast, matchingSpell, type ResolvedItemCast } from '@/lib/itemCast'
import { itemGrantedSpells } from '@/lib/itemMagic'
import SpellEffectAsk, { type SpellEffectPick } from '@/components/rules/SpellEffectAsk'
import type { CharacterFull, SpellEffectInfo, SpellEffectsResult } from '@/types'
import ItemCastSheet from '@/pages/spells/ItemCastSheet'

/** Lancio di un incantesimo concesso da un oggetto: niente slot, il BE scala le cariche. */
export function useItemCast(charId: number) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [resolved, setResolved] = useState<ResolvedItemCast | null>(null)
  const [effects, setEffects] = useState<SpellEffectsResult | undefined>()
  // Incantesimo dell'oggetto con effetto sui bersagli (catalogo): si chiede prima a chi va.
  const [ask, setAsk] = useState<{ itemId: number; spellIndex: number; name: string; level: number; effect: SpellEffectInfo } | null>(null)

  const mutation = useMutation({
    mutationFn: ({ itemId, spellIndex, pick }: { itemId: number; spellIndex: number; name: string; pick?: SpellEffectPick }) =>
      api.items.cast(charId, itemId, spellIndex, pick),
    onSuccess: (updated, { itemId, spellIndex }) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      const item = updated.items?.find((i) => i.id === itemId)
      setEffects(updated.spell_effects)
      setResolved(item ? resolveItemCast(updated, item, spellIndex) : null)
    },
    onError: (err) => {
      const detail = err instanceof ApiError && err.status === 409 ? String(err.detail) : ''
      if (detail === 'no_charges') toast.error(t('character.inventory.magic.no_charges'))
      else if (detail === 'not_enough_charges') toast.error(t('character.inventory.magic.not_enough_charges'))
      else if (detail === 'attunement_required') toast.error(t('character.inventory.magic.attunement_required'))
      else toast.error(t('common.action_failed'))
    },
  })

  const mutate = (vars: { itemId: number; spellIndex: number; name: string }) => {
    // Le informazioni sull'effetto stanno sull'incantesimo del personaggio con lo stesso indice SRD o nome: senza, si lancia su di sé.
    const char = qc.getQueryData<CharacterFull>(['character', charId])
    const item = char?.items?.find((i) => i.id === vars.itemId)
    const granted = item ? itemGrantedSpells(item)[vars.spellIndex] : undefined
    const effect = char && granted ? matchingSpell(char, granted)?.effect : undefined
    if (granted && effect && (effect.target_kind !== 'self' || effect.choices.length > 0)) setAsk({ ...vars, level: granted.level, effect })
    else mutation.mutate(vars)
  }

  return {
    mutate,
    isPending: mutation.isPending,
    variables: mutation.variables,
    elements: (
      <>
        {ask && (
          <SpellEffectAsk charId={charId} title={ask.name} effect={ask.effect} slotLevel={ask.level} onClose={() => setAsk(null)}
            onConfirm={(pick) => { const { effect: _e, level: _l, ...vars } = ask; setAsk(null); mutation.mutate({ ...vars, pick }) }} />
        )}
        {resolved && <ItemCastSheet charId={charId} resolved={resolved} effects={effects} onClose={() => setResolved(null)} />}
      </>
    ),
  }
}
