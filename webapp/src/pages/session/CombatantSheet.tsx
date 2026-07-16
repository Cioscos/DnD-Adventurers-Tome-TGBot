import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ArrowUp, ArrowDown, Trash2 } from 'lucide-react'
import { GiDeathSkull as Skull, GiHeartPlus as Heart } from 'react-icons/gi'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
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
  // patchMutation is shared by several distinct controls below (damage, heal,
  // per-condition toggles, initiative apply, mark dead). Its `variables`
  // shape alone can't disambiguate which control is in flight (e.g. damage
  // and heal both send `{ current_hp }`), so we track the initiating control
  // locally and clear it once the mutation settles.
  const [activeAction, setActiveAction] = useState<
    'damage' | 'heal' | 'initiative' | 'dead' | `cond:${string}` | null
  >(null)
  const [reorderDir, setReorderDir] = useState<-1 | 1 | null>(null)

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
    onSettled: () => setActiveAction(null),
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
    onSettled: () => setReorderDir(null),
  })

  const isFullMonster = c.kind === 'monster' && encounter.mode === 'full'
  const orderedIds = encounter.combatants.map((x) => x.id)
  const myIdx = orderedIds.indexOf(c.id)

  const move = (dir: -1 | 1) => {
    const target = myIdx + dir
    if (target < 0 || target >= orderedIds.length) return
    const next = [...orderedIds]
    ;[next[myIdx], next[target]] = [next[target], next[myIdx]]
    setReorderDir(dir)
    reorderMutation.mutate(next)
  }

  const applyHp = (sign: -1 | 1) => {
    const amt = Number(amount)
    if (!amt || amt <= 0 || c.current_hp === null) return
    setActiveAction(sign === -1 ? 'damage' : 'heal')
    patchMutation.mutate({ current_hp: Math.max(0, c.current_hp + sign * amt) })
    setAmount('')
  }

  const toggleCondition = (slug: string) => {
    const next: Record<string, unknown> = { ...c.conditions }
    if (next[slug]) delete next[slug]
    else next[slug] = true
    setActiveAction(`cond:${slug}`)
    patchMutation.mutate({ conditions: next })
  }

  const applyInitiative = () => {
    const v = Number(initiative)
    if (Number.isNaN(v) || initiative.trim() === '') return
    setActiveAction('initiative')
    patchMutation.mutate({ initiative: v })
    setInitiative('')
  }

  return (
    <Sheet open onClose={onClose} title={c.name}>
      <div className="p-1 space-y-4">
        {isFullMonster && c.current_hp !== null && (
          <section className="space-y-2">
            <p className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
              {t('session.combat.hp_controls')}: <span className="font-mono tabular-nums">{c.current_hp}/{c.max_hp}</span>
            </p>
            <div className="flex gap-2 items-stretch">
              <div className="w-24 shrink-0">
                <Input
                  type="number"
                  inputMode="numeric"
                  value={amount}
                  onChange={setAmount}
                  placeholder={t('session.combat.amount_placeholder')}
                  className="text-center font-mono"
                />
              </div>
              <Pressable
                onClick={() => applyHp(-1)}
                disabled={patchMutation.isPending && activeAction !== 'damage'}
                pending={patchMutation.isPending && activeAction === 'damage'}
                className="flex-1 min-h-[48px] px-3 py-2 rounded-md border border-dnd-crimson-bright/60
                           text-dnd-crimson-bright text-sm font-cinzel uppercase tracking-wider
                           active:opacity-70 disabled:opacity-40"
              >
                {t('session.combat.damage')}
              </Pressable>
              <Pressable
                onClick={() => applyHp(1)}
                disabled={patchMutation.isPending && activeAction !== 'heal'}
                pending={patchMutation.isPending && activeAction === 'heal'}
                className="flex-1 min-h-[48px] px-3 py-2 rounded-md border border-dnd-emerald-bright/60
                           text-dnd-emerald-bright text-sm font-cinzel uppercase tracking-wider
                           active:opacity-70 disabled:opacity-40"
              >
                <Heart size={13} className="inline mr-1" />
                {t('session.combat.heal')}
              </Pressable>
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
                const thisAction = `cond:${slug}` as const
                return (
                  <Pressable
                    key={slug}
                    onClick={() => toggleCondition(slug)}
                    aria-pressed={active}
                    disabled={patchMutation.isPending && activeAction !== thisAction}
                    pending={patchMutation.isPending && activeAction === thisAction}
                    spinnerSize={12}
                    className={`min-h-[44px] px-2.5 py-2 rounded-md border text-xs text-left break-words
                      ${active
                        ? 'border-dnd-amber bg-dnd-surface-raised text-dnd-amber'
                        : 'border-dnd-border bg-dnd-surface text-dnd-text-muted'}`}
                  >
                    {formatCondition(slug, true, t)}
                  </Pressable>
                )
              })}
            </div>
          </section>
        )}

        <section className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
            {t('session.combat.initiative_edit')}
          </p>
          <div className="flex gap-2 items-stretch">
            <div className="w-24 shrink-0">
              <Input
                type="number"
                inputMode="numeric"
                value={initiative}
                onChange={setInitiative}
                placeholder={String(c.initiative ?? '—')}
                className="text-center font-mono"
              />
            </div>
            <Pressable
              onClick={applyInitiative}
              disabled={(patchMutation.isPending && activeAction !== 'initiative') || initiative.trim() === ''}
              pending={patchMutation.isPending && activeAction === 'initiative'}
              className="flex-1 min-h-[48px] px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border
                         text-sm active:opacity-60 disabled:opacity-40"
            >
              {t('session.combat.apply')}
            </Pressable>
          </div>
        </section>

        {encounter.status === 'active' && (
          <section className="flex gap-2">
            <Pressable
              onClick={() => move(-1)}
              disabled={(reorderMutation.isPending && reorderDir !== -1) || myIdx <= 0}
              pending={reorderMutation.isPending && reorderDir === -1}
              className="flex-1 min-h-[44px] px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                         text-sm inline-flex items-center justify-center gap-1.5
                         active:opacity-60 disabled:opacity-40"
            >
              <ArrowUp size={14} /> {t('session.combat.move_up')}
            </Pressable>
            <Pressable
              onClick={() => move(1)}
              disabled={(reorderMutation.isPending && reorderDir !== 1) || myIdx >= orderedIds.length - 1}
              pending={reorderMutation.isPending && reorderDir === 1}
              className="flex-1 min-h-[44px] px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                         text-sm inline-flex items-center justify-center gap-1.5
                         active:opacity-60 disabled:opacity-40"
            >
              <ArrowDown size={14} /> {t('session.combat.move_down')}
            </Pressable>
          </section>
        )}

        <section className="flex gap-2 pt-2 border-t border-dnd-gold-dim/10">
          <Pressable
            onClick={() => {
              setActiveAction('dead')
              patchMutation.mutate({ is_dead: !c.is_dead })
            }}
            disabled={patchMutation.isPending && activeAction !== 'dead'}
            pending={patchMutation.isPending && activeAction === 'dead'}
            className="flex-1 min-h-[44px] px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                       text-sm inline-flex items-center justify-center gap-1.5
                       active:opacity-60 disabled:opacity-40"
          >
            <Skull size={14} />
            {c.is_dead ? t('session.combat.revive') : t('session.combat.mark_dead')}
          </Pressable>
          <Pressable
            onClick={() =>
              telegramConfirm(
                t('session.combat.remove_confirm', { name: c.name }),
                (ok) => ok && removeMutation.mutate(),
              )
            }
            pending={removeMutation.isPending}
            className="flex-1 min-h-[44px] px-3 py-2.5 rounded-md border border-dnd-crimson-bright/60
                       text-dnd-crimson-bright text-sm inline-flex items-center
                       justify-center gap-1.5 active:opacity-70 disabled:opacity-40"
          >
            <Trash2 size={14} /> {t('session.combat.remove')}
          </Pressable>
        </section>
      </div>
    </Sheet>
  )
}
