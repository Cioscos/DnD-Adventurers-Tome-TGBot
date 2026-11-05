import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Pressable from '@/components/ui/Pressable'
import { haptic } from '@/auth/telegram'
import { notifyMutationError } from '@/lib/mutationError'
import type { PendingChoice } from '@/types'

/** Personaggio salvato prima del catalogo (R39): segna quali incantesimi che conosce già sono i suoi Segreti Magici,
 *  senza aggiungerli né duplicarli. Il server li toglie dalla scelta in sospeso. */
export default function OwnedSecrets({ charId, pick }: { charId: number; pick: PendingChoice }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [picked, setPicked] = useState<number[]>([])
  const owned = pick.spell_pick?.owned ?? []
  const limit = pick.count ?? 1
  const mutation = useMutation({
    mutationFn: () => api.choices.resolve(charId, pick.id, { kind: 'class_option', options: picked.map(String) }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setPicked([])
      haptic.success()
    },
    onError: () => notifyMutationError(),
  })
  const toggle = (id: number) =>
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < limit ? [...cur, id] : cur))

  return (
    <div data-testid="spell-pick-owned" className="mt-3 space-y-2">
      <p className="font-body text-xs text-dnd-text-muted">{t('character.spells.pick_owned_title')}</p>
      {owned.map((s) => {
        const on = picked.includes(s.id)
        return (
          <Pressable key={s.id} onClick={() => toggle(s.id)} aria-pressed={on}
            className={`w-full min-h-[44px] px-3 py-2 rounded-xl border text-left text-sm font-body text-dnd-text ${
              on ? 'bg-dnd-gold/15 border-dnd-gold' : 'border-dnd-border'
            }`}>
            {s.name}
          </Pressable>
        )
      })}
      <Pressable onClick={() => mutation.mutate()} disabled={picked.length === 0} pending={mutation.isPending}
        className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40">
        {t('character.spells.pick_already_known')}
      </Pressable>
    </div>
  )
}
