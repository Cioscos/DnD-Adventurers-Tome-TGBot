import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ArrowUp, ArrowDown, Plus, Trash2, X } from 'lucide-react'
import { GiDeathSkull as Skull, GiHeartPlus as Heart } from 'react-icons/gi'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import IconButton from '@/components/ui/IconButton'
import AddConditionSheet from '@/pages/session/AddConditionSheet'
import { api } from '@/api/client'
import { haptic, telegramConfirm } from '@/auth/telegram'
import { formatCondition } from '@/lib/conditions'
import { formatExpiry, formatSave } from '@/lib/conditionEffects'
import type { CharacterLiveSnapshot, CombatantLive, CombatantPatch, EncounterLive } from '@/types'

interface Props {
  sessionId: number
  encounter: EncounterLive
  combatant: CombatantLive
  liveCharacters: CharacterLiveSnapshot[]
  onClose: () => void
}

export default function CombatantSheet({ sessionId, encounter, combatant: c, liveCharacters, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [amount, setAmount] = useState('')
  const [initiative, setInitiative] = useState('')
  // patchMutation is shared by several distinct controls below (damage, heal,
  // initiative apply, mark dead). Its `variables`
  // shape alone can't disambiguate which control is in flight (e.g. damage
  // and heal both send `{ current_hp }`), so we track the initiating control
  // locally and clear it once the mutation settles.
  const [activeAction, setActiveAction] = useState<
    'damage' | 'heal' | 'initiative' | 'dead' | null
  >(null)
  const [reorderDir, setReorderDir] = useState<-1 | 1 | null>(null)
  const [showAddCondition, setShowAddCondition] = useState(false)

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

  const removeConditionMutation = useMutation({
    mutationFn: (slug: string) => api.sessions.encounter.removeCondition(sessionId, c.id, slug),
    onSuccess: () => { haptic.light(); invalidate() },
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

  // PG: la fonte è la scheda (live_characters); mostri: il combattente.
  const snap = c.kind === 'pc' ? liveCharacters.find((s) => s.id === c.character_id) : undefined
  const conditions = (c.kind === 'pc' ? snap?.conditions : c.conditions) ?? {}
  const effects = (c.kind === 'pc' ? snap?.condition_effects : c.condition_effects) ?? []
  const activeConds = Object.entries(conditions).filter(([, v]) => Boolean(v))

  const applyInitiative = () => {
    const v = Number(initiative)
    if (Number.isNaN(v) || initiative.trim() === '') return
    setActiveAction('initiative')
    patchMutation.mutate({ initiative: v })
    setInitiative('')
  }

  return (
    <Sheet open onClose={onClose} title={c.name}>
      <div className="p-5 space-y-4">
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

        <section className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-dnd-gold-dim font-cinzel">
            {t('session.combat.active_conditions')}
          </p>
          {activeConds.length === 0 && (
            <p className="text-sm text-dnd-text-muted">{t('session.combat.no_conditions')}</p>
          )}
          {activeConds.map(([slug, val]) => {
            const eff = effects.find((e) => e.slug === slug)
            const label = slug.startsWith('custom:') ? slug.slice('custom:'.length) : formatCondition(slug, val, t)
            const details = eff
              ? [
                  formatExpiry(eff, t, c.name),
                  formatSave(eff, t, c.name),
                  eff.source_name && t('session.combat.source_label', { name: eff.source_name }),
                ].filter(Boolean)
              : []
            const removing = removeConditionMutation.isPending && removeConditionMutation.variables === slug
            return (
              <div
                key={slug}
                className="flex items-center gap-2 rounded-md border border-dnd-amber/50 bg-dnd-surface px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-dnd-amber break-words">{label}</p>
                  {details.map((d) => (
                    <p key={d as string} className="text-xs text-dnd-text-muted break-words">{d}</p>
                  ))}
                </div>
                <IconButton
                  icon={<X size={16} />}
                  aria-label={t('session.combat.remove_condition', { name: label })}
                  loading={removing}
                  disabled={removeConditionMutation.isPending && !removing}
                  onClick={() => removeConditionMutation.mutate(slug)}
                />
              </div>
            )
          })}
          <Pressable
            onClick={() => setShowAddCondition(true)}
            className="w-full min-h-[44px] px-3 py-2.5 rounded-md bg-dnd-surface border border-dnd-border
                       text-sm inline-flex items-center justify-center gap-1.5 active:opacity-60"
          >
            <Plus size={14} /> {t('session.combat.add_condition')}
          </Pressable>
        </section>

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
      {showAddCondition && (
        <AddConditionSheet
          sessionId={sessionId}
          encounter={encounter}
          target={c}
          liveCharacters={liveCharacters}
          onClose={() => setShowAddCondition(false)}
        />
      )}
    </Sheet>
  )
}
