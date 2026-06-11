import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ArrowUp, ArrowDown, Trash2 } from 'lucide-react'
import { GiDeathSkull as Skull, GiHeartPlus as Heart } from 'react-icons/gi'
import { api } from '@/api/client'
import { haptic, telegramConfirm } from '@/auth/telegram'
import { formatCondition } from '@/lib/conditions'
import type { CombatantLive, CombatantPatch, EncounterLive } from '@/types'

const STANDARD_CONDITIONS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'prone', 'restrained', 'stunned', 'unconscious',
] as const

interface Props {
  sessionId: number
  encounter: EncounterLive
  combatant: CombatantLive
  onClose: () => void
}

export default function CombatantSheet({ sessionId, encounter, combatant: c, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [amount, setAmount] = useState('')
  const [initiative, setInitiative] = useState('')

  const invalidate = () => qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
  const onError = () => {
    haptic.error()
    toast.error(t('session.combat.action_failed'))
  }

  const patchMutation = useMutation({
    mutationFn: (patch: CombatantPatch) =>
      api.sessions.encounter.patchCombatant(sessionId, c.id, patch),
    onSuccess: () => { haptic.success(); invalidate() },
    onError,
  })

  const removeMutation = useMutation({
    mutationFn: () => api.sessions.encounter.removeCombatant(sessionId, c.id),
    onSuccess: () => { haptic.warning(); invalidate(); onClose() },
    onError,
  })

  const reorderMutation = useMutation({
    mutationFn: (ids: number[]) => api.sessions.encounter.reorder(sessionId, ids),
    onSuccess: () => { haptic.light(); invalidate() },
    onError,
  })

  const isFullMonster = c.kind === 'monster' && encounter.mode === 'full'
  const orderedIds = encounter.combatants.map((x) => x.id)
  const myIdx = orderedIds.indexOf(c.id)

  const move = (dir: -1 | 1) => {
    const target = myIdx + dir
    if (target < 0 || target >= orderedIds.length) return
    const next = [...orderedIds]
    ;[next[myIdx], next[target]] = [next[target], next[myIdx]]
    reorderMutation.mutate(next)
  }

  const applyHp = (sign: -1 | 1) => {
    const amt = Number(amount)
    if (!amt || amt <= 0 || c.current_hp === null) return
    patchMutation.mutate({ current_hp: Math.max(0, c.current_hp + sign * amt) })
    setAmount('')
  }

  const toggleCondition = (slug: string) => {
    const next: Record<string, unknown> = { ...c.conditions }
    if (next[slug]) delete next[slug]
    else next[slug] = true
    patchMutation.mutate({ conditions: next })
  }

  const applyInitiative = () => {
    const v = Number(initiative)
    if (Number.isNaN(v) || initiative.trim() === '') return
    patchMutation.mutate({ initiative: v })
    setInitiative('')
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold font-cinzel text-dnd-gold break-words">{c.name}</h3>
          <button onClick={onClose} className="text-dnd-text-secondary text-sm" aria-label={t('common.close')}>
            &#x2715;
          </button>
        </div>

        {isFullMonster && c.current_hp !== null && (
          <section className="space-y-2">
            <p className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
              {t('session.combat.hp_controls')}: <span className="font-mono tabular-nums">{c.current_hp}/{c.max_hp}</span>
            </p>
            <div className="flex gap-2">
              <input
                type="number"
                inputMode="numeric"
                value={amount}
                placeholder={t('session.combat.amount_placeholder')}
                onChange={(e) => setAmount(e.target.value)}
                className="w-20 rounded-md bg-dnd-surface border border-dnd-border px-3 py-2.5
                           text-sm text-center font-mono tabular-nums"
              />
              <button
                type="button"
                onClick={() => applyHp(-1)}
                disabled={patchMutation.isPending}
                className="flex-1 px-3 py-2 rounded-md border border-[var(--dnd-crimson-bright)]/60
                           text-[var(--dnd-crimson-bright)] text-sm font-cinzel uppercase tracking-wider
                           active:opacity-70 disabled:opacity-40"
              >
                {t('session.combat.damage')}
              </button>
              <button
                type="button"
                onClick={() => applyHp(1)}
                disabled={patchMutation.isPending}
                className="flex-1 px-3 py-2 rounded-md border border-[var(--dnd-emerald-bright)]/60
                           text-[var(--dnd-emerald-bright)] text-sm font-cinzel uppercase tracking-wider
                           active:opacity-70 disabled:opacity-40"
              >
                <Heart size={13} className="inline mr-1" />
                {t('session.combat.heal')}
              </button>
            </div>
          </section>
        )}

        {c.kind === 'monster' && (
          <section className="space-y-2">
            <p className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
              {t('session.combat.conditions_title')}
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              {STANDARD_CONDITIONS.map((slug) => {
                const active = Boolean(c.conditions[slug])
                return (
                  <button
                    key={slug}
                    type="button"
                    onClick={() => toggleCondition(slug)}
                    className={`px-2.5 py-2 rounded-md border text-xs text-left break-words
                      ${active
                        ? 'border-dnd-amber bg-dnd-surface-raised text-dnd-amber'
                        : 'border-dnd-border bg-dnd-surface text-dnd-text-muted'}`}
                  >
                    {formatCondition(slug, true, t)}
                  </button>
                )
              })}
            </div>
          </section>
        )}

        <section className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
            {t('session.combat.initiative_edit')}
          </p>
          <div className="flex gap-2">
            <input
              type="number"
              inputMode="numeric"
              value={initiative}
              placeholder={String(c.initiative ?? '—')}
              onChange={(e) => setInitiative(e.target.value)}
              className="w-20 rounded-md bg-dnd-surface border border-dnd-border px-3 py-2.5
                         text-sm text-center font-mono tabular-nums"
            />
            <button
              type="button"
              onClick={applyInitiative}
              disabled={patchMutation.isPending || initiative.trim() === ''}
              className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border
                         text-sm active:opacity-60 disabled:opacity-40"
            >
              {t('session.combat.apply')}
            </button>
          </div>
        </section>

        {encounter.status === 'active' && (
          <section className="flex gap-2">
            <button
              type="button"
              onClick={() => move(-1)}
              disabled={reorderMutation.isPending || myIdx <= 0}
              className="flex-1 px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                         text-sm inline-flex items-center justify-center gap-1.5
                         active:opacity-60 disabled:opacity-40"
            >
              <ArrowUp size={14} /> {t('session.combat.move_up')}
            </button>
            <button
              type="button"
              onClick={() => move(1)}
              disabled={reorderMutation.isPending || myIdx >= orderedIds.length - 1}
              className="flex-1 px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                         text-sm inline-flex items-center justify-center gap-1.5
                         active:opacity-60 disabled:opacity-40"
            >
              <ArrowDown size={14} /> {t('session.combat.move_down')}
            </button>
          </section>
        )}

        <section className="flex gap-2 pt-2 border-t border-dnd-gold-dim/10">
          <button
            type="button"
            onClick={() => patchMutation.mutate({ is_dead: !c.is_dead })}
            disabled={patchMutation.isPending}
            className="flex-1 px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                       text-sm inline-flex items-center justify-center gap-1.5
                       active:opacity-60 disabled:opacity-40"
          >
            <Skull size={14} />
            {c.is_dead ? t('session.combat.revive') : t('session.combat.mark_dead')}
          </button>
          <button
            type="button"
            onClick={() =>
              telegramConfirm(
                t('session.combat.remove_confirm', { name: c.name }),
                (ok) => ok && removeMutation.mutate(),
              )
            }
            disabled={removeMutation.isPending}
            className="flex-1 px-3 py-2.5 rounded-md border border-[var(--dnd-crimson-bright)]/60
                       text-[var(--dnd-crimson-bright)] text-sm inline-flex items-center
                       justify-center gap-1.5 active:opacity-70 disabled:opacity-40"
          >
            <Trash2 size={14} /> {t('session.combat.remove')}
          </button>
        </section>
      </div>
    </div>
  )
}
