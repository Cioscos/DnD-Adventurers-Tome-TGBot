import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { notifyMutationError } from '@/lib/mutationError'
import type { CharacterFull } from '@/types'

const KEY = 'paladin.undying_sentinel'

/** A 0 PF, il paladino degli Antichi con l'uso ancora disponibile può restare a 1 PF (Sentinella Imperitura).
 *  Il server decide se vale (non a danno letale sul colpo) e spende l'uso. */
export default function UndyingSentinelOffer({ charId, char }: { charId: number; char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const use = useMutation({
    mutationFn: () => api.characters.featureUse(charId, KEY),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      toast.success(t('character.hp.sentinel_title'))
    },
    onError: () => notifyMutationError(),
  })
  const row = char.abilities?.find((a) => a.feature_key === KEY)
  if (!row || (row.uses ?? 0) < 1 || char.is_dead || char.current_hit_points > 0) return null
  return (
    <Surface variant="elevated">
      <p className="mb-1 text-xs font-cinzel uppercase tracking-wider text-dnd-gold-bright">{t('character.hp.sentinel_title')}</p>
      <p className="mb-3 text-sm font-body text-dnd-text">{t('character.hp.sentinel_body')}</p>
      <Button size="sm" variant="primary" className="min-h-11" loading={use.isPending} onClick={() => use.mutate()}>
        {t('character.hp.sentinel_cta')}
      </Button>
    </Surface>
  )
}
