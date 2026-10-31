import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import Surface from '@/components/ui/Surface'
import Pressable from '@/components/ui/Pressable'
import { MAX_ATTUNED, isAttuned, requiresAttunement } from '@/lib/itemMagic'
import type { Item } from '@/types'

interface Props {
  charId: number
  items: Item[]
}

/** 3 slot di sintonia in cima all'inventario; sintonizza/rimuove rimandando il metadata intero. */
export default function AttunementSection({ charId, items }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const attuned = items.filter(isAttuned)
  const candidates = items.filter((i) => requiresAttunement(i) && !isAttuned(i))

  const mutation = useMutation({
    mutationFn: ({ item, value }: { item: Item; value: boolean }) =>
      api.items.update(charId, item.id, { item_metadata: { ...(item.item_metadata ?? {}), attuned: value } }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setError(null)
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        setError(t('character.inventory.magic.attunement_limit'))
        haptic.error()
      } else {
        setError(t('common.action_failed'))
      }
    },
  })

  if (attuned.length === 0 && candidates.length === 0) return null

  const slots = Array.from({ length: MAX_ATTUNED }, (_, i) => attuned[i] ?? null)
  const rowCls = 'w-full min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl border text-left text-sm font-body'

  return (
    <Surface variant="elevated" className="!py-2 space-y-2">
      <div className="flex items-center gap-2 text-dnd-gold">
        <Sparkles size={13} />
        <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
          {t('character.inventory.magic.attunement_title')}
        </p>
        <span className="text-xs font-mono tabular-nums text-dnd-text-muted">
          {attuned.length}/{MAX_ATTUNED}
        </span>
      </div>

      <div className="space-y-1">
        {slots.map((item, i) => (
          <div key={item?.id ?? `empty-${i}`} data-testid="attunement-slot">
          {item ? (
            <Pressable
              onClick={() => mutation.mutate({ item, value: false })}
              pending={mutation.isPending && mutation.variables?.item.id === item.id}
              aria-label={`${t('character.inventory.magic.unattune')} ${item.name}`}
              className={`${rowCls} bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright`}
            >
              <span className="flex-1 min-w-0 truncate">{item.name}</span>
              <span className="text-xs text-dnd-text-muted shrink-0">{t('character.inventory.magic.unattune')}</span>
            </Pressable>
          ) : (
            <div
              data-testid="attunement-slot-empty"
              className={`${rowCls} bg-dnd-surface border-dashed border-dnd-border text-dnd-text-faint italic`}
            >
              {t('character.inventory.magic.slot_empty')}
            </div>
          )}
          </div>
        ))}
      </div>

      {candidates.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-dnd-text-muted font-body">{t('character.inventory.magic.attunable')}</p>
          {candidates.map((item) => (
            <Pressable
              key={item.id}
              onClick={() => mutation.mutate({ item, value: true })}
              pending={mutation.isPending && mutation.variables?.item.id === item.id}
              aria-label={`${t('character.inventory.magic.attune')} ${item.name}`}
              className={`${rowCls} bg-dnd-surface border-dnd-border text-dnd-text`}
            >
              <span className="flex-1 min-w-0 truncate">{item.name}</span>
              <span className="text-xs text-dnd-gold shrink-0">{t('character.inventory.magic.attune')}</span>
            </Pressable>
          ))}
        </div>
      )}

      {error && <p role="alert" className="text-xs text-dnd-crimson-bright font-body">{error}</p>}
    </Surface>
  )
}
