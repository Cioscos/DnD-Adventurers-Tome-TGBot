import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { conditionLabel } from '@/lib/conditions'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type TargetEffect } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { useToast } from '@/hooks/useToast'
import { notifyMutationError } from '@/lib/mutationError'

type Props = { charId: number; effectKey: string; onClose: () => void }

/** Esito di un effetto confermato col tiro (condizione, TS, durata) e scelta del combattente a cui applicarlo.
 *  Fuori da un incontro attivo mostra solo l'esito. */
export default function TargetEffectSheet({ charId, effectKey, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const { data } = useQuery({
    queryKey: ['target-effect', charId, effectKey],
    queryFn: () => api.characters.targetEffectPreview(charId, effectKey),
  })
  const apply = useMutation({
    mutationFn: (combatantId: number) => api.characters.targetEffectApply(charId, effectKey, combatantId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      toast.success(t(res.applied ? (res.pending_save_id ? 'character.target_effect.applied_save' : 'character.target_effect.applied') : 'character.target_effect.nothing', { name: res.target_name }))
      onClose()
    },
    onError: () => notifyMutationError(),
  })
  const fx = data?.result
  return (
    <Sheet open onClose={onClose} title={t('character.target_effect.title')} zClassName="z-[60]">
      {fx && (
        <div className="flex flex-col gap-3 px-4 pb-4">
          <ul className="flex flex-col gap-1 text-sm font-body text-dnd-text">
            {fx.condition && <li className="font-bold">{[fx.condition, ...(fx.also ?? [])].map((c) => conditionName(t, c)).join(' + ')}</li>}
            <li>{fx.save_ability && fx.save_dc != null
              ? t('character.target_effect.save', { ability: t(`common.abilities.${fx.save_ability}`), dc: fx.save_dc })
              : t('character.target_effect.no_save')}</li>
            {(fx.condition || fx.ends_at || fx.rounds) && <li className="text-dnd-text-muted">{durationText(t, fx)}</li>}
            {fx.condition?.startsWith('custom:') && (
              <li className="text-dnd-text-muted">{t(`character.target_effect.custom_note.${fx.condition.slice(7)}`, { defaultValue: '' })}</li>
            )}
            {fx.damage_dice && <li className="tabular-nums">{fx.damage_dice}</li>}
            {fx.note && <li className="text-xs text-dnd-text-muted">{t(`character.target_effect.notes.${fx.note}`, { defaultValue: '' })}</li>}
            {fx.repeat_save && <li className="text-xs text-dnd-text-muted">{t(`character.target_effect.repeat_save_${fx.repeat_save}`)}</li>}
            {fx.extends && <li className="text-xs text-dnd-text-muted">{t('character.target_effect.extends_note')}</li>}
            {fx.immune_on_success && <li className="text-xs text-dnd-text-muted">{t('character.target_effect.immune_note')}</li>}
          </ul>
          {data.combatants.length === 0 ? (
            <p className="text-sm font-body text-dnd-text-muted">{t('character.target_effect.no_encounter')}</p>
          ) : (
            <>
              <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.target_effect.pick')}</p>
              <div className="flex flex-col gap-2">
                {data.combatants.map((c) => (
                  <Button
                    key={c.id} variant="secondary" className="justify-start break-words text-left"
                    loading={apply.isPending && apply.variables === c.id} disabled={apply.isPending || !!c.immune}
                    onClick={() => apply.mutate(c.id)}
                  >
                    {c.name}
                    {c.immune && <span className="ml-2 text-xs font-normal text-dnd-text-muted">{t('character.target_effect.immune')}</span>}
                  </Button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </Sheet>
  )
}

type T = (key: string, opts?: Record<string, unknown>) => string

function conditionName(t: T, slug: string): string {
  return conditionLabel(slug, t as unknown as TFunction)
}

function durationText(t: T, fx: TargetEffect): string {
  if (fx.ends_at?.anchor === 'source' && fx.ends_at.edge === 'start') return t('character.target_effect.until_my_turn')
  if (fx.ends_at?.anchor === 'active') return t('character.target_effect.until_current_turn_end')
  const rounds = fx.ends_at?.count ?? fx.rounds
  if (rounds) return t('character.target_effect.until_turn_end', { count: rounds })
  return t(fx.ends_with_concentration ? 'character.target_effect.while_concentrating' : 'character.target_effect.no_duration')
}
