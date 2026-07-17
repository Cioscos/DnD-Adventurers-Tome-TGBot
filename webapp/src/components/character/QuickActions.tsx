import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Check, Minus } from 'lucide-react'
import {
  GiCrossedSwords, GiShieldEchoes, GiSpellBook, GiLightningStorm,
  GiLightningTrio, GiAbacus, GiPolarStar, GiArrowhead,
  GiDiceSixFacesOne, GiNightSleep, GiCampfire,
} from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import IconButton from '@/components/ui/IconButton'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import UsesEditSheet from '@/components/ui/UsesEditSheet'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import { haptic } from '@/auth/telegram'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useToast } from '@/hooks/useToast'
import { showUndoToast } from '@/components/ui/UndoToast'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import {
  readQuickActions,
  resolveQuickActions,
  quickActionKey,
  QUICK_ACTIONS_MAX,
  SAVE_ABILITIES,
  type QuickActionEntry,
  type ResolvedQuickAction,
} from '@/lib/quickActions'
import type { HitDiceSpendResult } from '@/api/client'
import type { CharacterFull, Ability, CharacterClass, Item } from '@/types'

interface Props {
  char: CharacterFull
}

type AttackState = { result: WeaponAttackResult; itemId: number; wasRerolled: boolean }
type SaveRollState = { result: RollResult; ability: string; wasRerolled: boolean }
type CounterEditState = { kind: 'ability'; ability: Ability } | { kind: 'ammo'; item: Item }
type EditorGroup = { labelKey: string; rows: { entry: QuickActionEntry; label: string }[]; emptyKey: string | null }

const TYPE_ICONS = {
  weapon: GiCrossedSwords,
  save: GiShieldEchoes,
  spell: GiSpellBook,
  ability: GiLightningTrio,
  counter_ability: GiAbacus,
  counter_inspiration: GiPolarStar,
  counter_ammo: GiArrowhead,
  hit_die: GiDiceSixFacesOne,
  rest: GiNightSleep,
} as const

export default function QuickActions({ char }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const castFlow = useCastFlow(char.id, char)

  const [editorOpen, setEditorOpen] = useState(false)
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const [saveState, setSaveState] = useState<SaveRollState | null>(null)
  const [confirmHitDie, setConfirmHitDie] = useState<{ cls: CharacterClass; remaining: number } | null>(null)
  const [hitDieResult, setHitDieResult] = useState<HitDiceSpendResult | null>(null)
  const [confirmLongRest, setConfirmLongRest] = useState(false)
  const [shortRestOpen, setShortRestOpen] = useState(false)
  const [counterEdit, setCounterEdit] = useState<CounterEditState | null>(null)

  const settings = (char.settings as Record<string, unknown>) ?? {}
  const entries = readQuickActions(settings)
  const resolved = resolveQuickActions(char, entries)

  const settingsMutation = useMutation({
    mutationFn: (next: QuickActionEntry[]) =>
      api.characters.update(char.id, { settings: { ...settings, quick_actions: next } }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const attackMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(char.id, itemId),
    onSuccess: (result, itemId) => {
      setAttackState({ result, itemId, wasRerolled: false })
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const attackRerollMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(char.id, itemId, true),
    onSuccess: (result) => {
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', char.id] })
      } else {
        haptic.error()
      }
    },
  })

  const rollSaveDie = async (): Promise<number | undefined> => {
    if (animate3d && !reducedMotion) {
      const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
      return detected[0]?.value
    }
    return undefined
  }

  const saveMutation = useMutation({
    mutationFn: async (ability: string) => {
      const die = await rollSaveDie()
      const result = await api.characters.rollSavingThrow(char.id, ability, die)
      return { result, ability }
    },
    onSuccess: ({ result, ability }) => {
      setSaveState({ result, ability, wasRerolled: false })
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const saveRerollMutation = useMutation({
    mutationFn: async (ability: string) => {
      const die = await rollSaveDie()
      return api.characters.rollSavingThrow(char.id, ability, die, true)
    },
    onSuccess: (result) => {
      setSaveState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', char.id] })
      } else {
        haptic.error()
      }
    },
  })

  const inspirationMutation = useMutation({
    mutationFn: (value: boolean) => api.characters.updateInspiration(char.id, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const ammoMutation = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) =>
      api.items.update(char.id, itemId, { quantity }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', char.id] }),
    onError: () => haptic.error(),
  })

  const usesMutation = useMutation({
    mutationFn: ({ abilityId, uses }: { abilityId: number; uses: number }) =>
      api.abilities.update(char.id, abilityId, { uses }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', char.id] }),
    onError: () => haptic.error(),
  })

  const consumeAbility = (ability: Ability) => {
    const current = ability.uses ?? 0
    if (current <= 0) {
      toast.error(t('character.quick_actions.ability_depleted'))
      return
    }
    usesMutation.mutate(
      { abilityId: ability.id, uses: current - 1 },
      {
        onSuccess: () => {
          showUndoToast({
            message: t('character.quick_actions.ability_used_toast', {
              name: ability.name, current: current - 1, max: ability.max_uses ?? 0,
            }),
            actionLabel: t('character.quick_actions.undo'),
            onUndo: () => usesMutation.mutate({ abilityId: ability.id, uses: current }),
          })
        },
      },
    )
  }

  const hitDieMutation = useMutation({
    mutationFn: ({ classId, count }: { classId: number; count: number }) =>
      api.characters.spendHitDice(char.id, classId, count),
    onSuccess: (result) => {
      setConfirmHitDie(null)
      setHitDieResult(result)
      qc.invalidateQueries({ queryKey: ['character', char.id] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.quick_actions.hit_die_exhausted'))
        qc.invalidateQueries({ queryKey: ['character', char.id] })
        setConfirmHitDie(null)
      } else {
        haptic.error()
      }
    },
  })

  const restMutation = useMutation({
    mutationFn: (restType: 'long' | 'short') => api.characters.rest(char.id, restType),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      setConfirmLongRest(false)
      setShortRestOpen(false)
      toast.success(t('character.quick_actions.rest_done'))
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const run = (action: ResolvedQuickAction) => {
    haptic.light()
    switch (action.type) {
      case 'weapon': attackMutation.mutate(action.item.id); break
      case 'save': saveMutation.mutate(action.ability); break
      case 'spell': castFlow.beginCast(action.spell); break
      case 'ability': consumeAbility(action.ability); break
      case 'hit_die':
        if (action.remaining > 0) setConfirmHitDie({ cls: action.cls, remaining: action.remaining })
        break
      case 'rest':
        if (action.rest === 'long') setConfirmLongRest(true)
        else setShortRestOpen(true)
        break
      default: break // i contatori hanno i propri bottoni, non passano da run
    }
  }

  const toggleEntry = (entry: QuickActionEntry) => {
    const key = quickActionKey(entry)
    const exists = entries.some((e) => quickActionKey(e) === key)
    if (exists) {
      settingsMutation.mutate(entries.filter((e) => quickActionKey(e) !== key))
    } else {
      if (entries.length >= QUICK_ACTIONS_MAX) {
        toast.error(t('character.quick_actions.max_reached', { max: QUICK_ACTIONS_MAX }))
        return
      }
      settingsMutation.mutate([...entries, entry])
    }
  }

  const isPinned = (entry: QuickActionEntry) => {
    const key = quickActionKey(entry)
    return entries.some((e) => quickActionKey(e) === key)
  }

  // Mutazione condivisa fra tutte le righe pin/unpin dell'editor (P4): `variables`
  // è la lista risultante (non l'entry cliccata), quindi deriviamo la chiave
  // toggled per differenza simmetrica rispetto a `entries` (una sola voce cambia
  // per chiamata, per costruzione di toggleEntry).
  const pendingToggleKey = (() => {
    if (!settingsMutation.isPending || !settingsMutation.variables) return null
    const nextKeys = new Set(settingsMutation.variables.map(quickActionKey))
    const curKeys = new Set(entries.map(quickActionKey))
    for (const k of nextKeys) if (!curKeys.has(k)) return k
    for (const k of curKeys) if (!nextKeys.has(k)) return k
    return null
  })()

  const isActionPending = (a: ResolvedQuickAction): boolean => {
    if (a.type === 'weapon') return attackMutation.isPending && attackMutation.variables === a.item.id
    if (a.type === 'save') return saveMutation.isPending && saveMutation.variables === a.ability
    if (a.type === 'spell') return castFlow.isSpellPending(a.spell.id)
    if (a.type === 'ability') return usesMutation.isPending && usesMutation.variables?.abilityId === a.ability.id
    return false
  }

  const actionLabel = (a: ResolvedQuickAction): string => {
    switch (a.type) {
      case 'weapon': return a.item.name
      case 'save': return t(`character.stats.${a.ability}`)
      case 'spell': return a.spell.name
      case 'ability': case 'counter_ability': return a.ability.name
      case 'counter_inspiration': return t('character.quick_actions.inspiration')
      case 'counter_ammo': return a.item.name
      case 'hit_die': return `d${a.cls.hit_die ?? 8} · ${a.cls.class_name}`
      case 'rest': return t(`character.quick_actions.rest_${a.rest}`)
    }
  }

  const weapons = (char.items ?? []).filter((i) => i.item_type === 'weapon')
  const spells = char.spells ?? []
  // Mirrors resolveQuickActions' isPinnableAbility() in lib/quickActions.ts: solo
  // abilità attive (non passive) con un tetto di usi possono essere pinnate.
  const pinnableAbilities = (char.abilities ?? []).filter((a) => !a.is_passive && a.max_uses != null)
  const ammoItems = (char.items ?? []).filter((i) => i.item_type === 'ammunition')

  // Gruppi editor "generici" (una riga = un pin/unpin): il blocco abilità (doppio
  // pin per riga) è renderizzato a parte fra questi due, quindi l'elenco è diviso
  // in top (prima delle abilità) e bottom (dopo, contatori incluso).
  const editorGroupsTop: EditorGroup[] = [
    {
      labelKey: 'character.quick_actions.group_weapons',
      rows: weapons.map((w) => ({
        entry: { type: 'weapon', id: w.id } as QuickActionEntry,
        label: w.name,
      })),
      emptyKey: 'character.quick_actions.no_weapons',
    },
    {
      labelKey: 'character.quick_actions.group_saves',
      rows: SAVE_ABILITIES.map((ability) => ({
        entry: { type: 'save', ability } as QuickActionEntry,
        label: t(`character.stats.${ability}`),
      })),
      emptyKey: null,
    },
    {
      labelKey: 'character.quick_actions.group_spells',
      rows: spells.map((s) => ({
        entry: { type: 'spell', id: s.id } as QuickActionEntry,
        label: s.name,
      })),
      emptyKey: 'character.quick_actions.no_spells',
    },
  ]

  const editorGroupsBottom: EditorGroup[] = [
    {
      labelKey: 'character.quick_actions.group_counters',
      rows: [
        { entry: { type: 'counter_inspiration' } as QuickActionEntry, label: t('character.quick_actions.inspiration') },
        ...ammoItems.map((it) => ({
          entry: { type: 'counter_ammo', id: it.id } as QuickActionEntry,
          label: it.name,
        })),
        ...(char.classes ?? []).map((cls) => ({
          entry: { type: 'hit_die', classId: cls.id } as QuickActionEntry,
          label: `${t('character.quick_actions.spend_hit_die_title')} · d${cls.hit_die ?? 8} ${cls.class_name}`,
        })),
      ],
      emptyKey: null,
    },
    {
      labelKey: 'character.quick_actions.group_rests',
      rows: (['long', 'short'] as const).map((rest) => ({
        entry: { type: 'rest', rest } as QuickActionEntry,
        label: t(`character.quick_actions.rest_${rest}`),
      })),
      emptyKey: null,
    },
  ]

  const renderGroup = (group: EditorGroup) => (
    <div key={group.labelKey}>
      <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim mb-1 px-1">
        {t(group.labelKey)}
      </p>
      {group.rows.length === 0 ? (
        group.emptyKey && (
          <p className="text-xs text-dnd-text-faint font-body italic px-1">
            {t(group.emptyKey)}
          </p>
        )
      ) : (
        <div className="space-y-1">
          {group.rows.map(({ entry, label }) => {
            const pinned = isPinned(entry)
            return (
              <Pressable
                key={quickActionKey(entry)}
                type="button"
                onClick={() => toggleEntry(entry)}
                pending={pendingToggleKey === quickActionKey(entry)}
                className={`w-full min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl border text-left
                  ${pinned
                    ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text'}`}
              >
                <span className="flex-1 min-w-0 truncate text-sm font-body">{label}</span>
                {pinned && <Check size={16} className="shrink-0" />}
              </Pressable>
            )
          })}
        </div>
      )}
    </div>
  )

  return (
    <>
      <Surface variant="elevated">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-dnd-gold">
            <GiLightningStorm size={16} />
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.quick_actions.title')}
            </p>
          </div>
          <Pressable
            type="button"
            onClick={() => { haptic.light(); setEditorOpen(true) }}
            whileTap={{ scale: 0.9 }}
            aria-label={t('character.quick_actions.edit')}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/40 text-dnd-gold-bright"
          >
            <Plus size={16} />
          </Pressable>
        </div>

        {resolved.length === 0 ? (
          <p className="text-xs text-dnd-text-muted font-body italic">
            {t('character.quick_actions.empty_hint')}
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {resolved.map((a, i) => {
              const spanFull = resolved.length % 2 === 1 && i === resolved.length - 1
              if (a.type === 'counter_inspiration') {
                return (
                  <Pressable
                    key={a.key}
                    type="button"
                    pending={inspirationMutation.isPending}
                    onClick={() => inspirationMutation.mutate(!a.active)}
                    whileTap={{ scale: 0.96 }}
                    aria-pressed={a.active}
                    className={`min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl border text-left
                      ${a.active
                        ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'
                        : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}
                      ${spanFull ? 'col-span-2' : ''}`}
                  >
                    <GiPolarStar size={16} className="shrink-0" />
                    <span className="flex-1 min-w-0 truncate text-sm font-body">
                      {actionLabel(a)}
                    </span>
                    <Check size={14} className={`shrink-0 ${a.active ? '' : 'opacity-0'}`} />
                  </Pressable>
                )
              }
              if (a.type === 'counter_ability' || a.type === 'counter_ammo') {
                const isAbility = a.type === 'counter_ability'
                const current = isAbility ? (a.ability.uses ?? 0) : (a.item.quantity ?? 0)
                const max = isAbility ? (a.ability.max_uses ?? 0) : null
                const rowPending = isAbility
                  ? usesMutation.isPending && usesMutation.variables?.abilityId === a.ability.id
                  : ammoMutation.isPending && ammoMutation.variables?.itemId === a.item.id
                const change = (next: number) => {
                  if (isAbility) usesMutation.mutate({ abilityId: a.ability.id, uses: next })
                  else ammoMutation.mutate({ itemId: a.item.id, quantity: next })
                }
                const Icon = TYPE_ICONS[a.type]
                return (
                  <div
                    key={a.key}
                    className={`min-h-[44px] flex items-center gap-1.5 px-2 py-1.5 rounded-xl
                                bg-dnd-surface border border-dnd-border ${spanFull ? 'col-span-2' : ''}`}
                  >
                    <Icon size={14} className="text-dnd-gold shrink-0" />
                    <span className="flex-1 min-w-0 truncate text-xs text-dnd-text font-body">
                      {actionLabel(a)}
                    </span>
                    <IconButton
                      icon={<Minus size={12} />}
                      onClick={() => change(Math.max(0, current - 1))}
                      loading={rowPending}
                      disabled={current <= 0}
                      haptic="light"
                      aria-label={`${actionLabel(a)} -1`}
                      className="w-8 h-8 rounded-lg bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/30 disabled:opacity-30"
                    />
                    <Pressable
                      type="button"
                      onClick={() => setCounterEdit(isAbility ? { kind: 'ability', ability: a.ability } : { kind: 'ammo', item: a.item })}
                      whileTap={{ scale: 0.92 }}
                      aria-label={t('character.abilities.set_uses_title')}
                      className="min-w-[44px] text-center font-mono font-bold tabular-nums text-sm text-dnd-gold-bright"
                    >
                      {current}{max != null ? <span className="text-dnd-text-muted text-[10px]">/{max}</span> : null}
                    </Pressable>
                    <IconButton
                      icon={<Plus size={12} />}
                      onClick={() => change(max != null ? Math.min(max, current + 1) : current + 1)}
                      loading={rowPending}
                      disabled={max != null && current >= max}
                      haptic="light"
                      aria-label={`${actionLabel(a)} +1`}
                      className="w-8 h-8 rounded-lg bg-dnd-emerald/15 text-dnd-emerald-bright border border-dnd-emerald/30 disabled:opacity-30"
                    />
                  </div>
                )
              }
              const Icon = TYPE_ICONS[a.type === 'rest' && a.rest === 'short' ? 'rest' : a.type]
              const RestIcon = a.type === 'rest' && a.rest === 'short' ? GiCampfire : Icon
              const depleted =
                (a.type === 'ability' && (a.ability.uses ?? 0) <= 0) ||
                (a.type === 'hit_die' && a.remaining <= 0)
              return (
                <Pressable
                  key={a.key}
                  type="button"
                  pending={isActionPending(a)}
                  onClick={() => run(a)}
                  whileTap={{ scale: 0.96 }}
                  className={`min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl
                              bg-dnd-surface border border-dnd-border text-left
                              disabled:opacity-60 ${depleted ? 'opacity-50' : ''} ${spanFull ? 'col-span-2' : ''}`}
                >
                  <RestIcon size={16} className="text-dnd-gold shrink-0" />
                  <span className="flex-1 min-w-0 truncate text-sm text-dnd-text font-body">
                    {actionLabel(a)}
                  </span>
                  {a.type === 'ability' && (
                    <span className="text-[10px] font-mono tabular-nums text-dnd-text-muted shrink-0">
                      {a.ability.uses ?? 0}/{a.ability.max_uses ?? 0}
                    </span>
                  )}
                  {a.type === 'hit_die' && (
                    <span className="text-[10px] font-mono tabular-nums text-dnd-text-muted shrink-0">
                      {a.remaining}/{a.cls.level}
                    </span>
                  )}
                </Pressable>
              )
            })}
          </div>
        )}
      </Surface>

      {/* Editor */}
      <Sheet
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        title={t('character.quick_actions.editor_title')}
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto scrollbar-hide">
          <p className="text-xs text-dnd-text-muted font-body italic">
            {t('character.quick_actions.editor_hint', { max: QUICK_ACTIONS_MAX, count: entries.length })}
          </p>

          {editorGroupsTop.map(renderGroup)}

          <div>
            <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim mb-1 px-1">
              {t('character.quick_actions.group_abilities')}
            </p>
            {pinnableAbilities.length === 0 ? (
              <p className="text-xs text-dnd-text-faint font-body italic px-1">
                {t('character.quick_actions.no_abilities')}
              </p>
            ) : (
              <div className="space-y-1">
                {pinnableAbilities.map((a) => {
                  const actionEntry: QuickActionEntry = { type: 'ability', id: a.id }
                  const counterEntry: QuickActionEntry = { type: 'counter_ability', id: a.id }
                  const actionPinned = isPinned(actionEntry)
                  const counterPinned = isPinned(counterEntry)
                  // Pin mutuamente esclusivi: attivarne uno rimuove l'altro.
                  const toggleExclusive = (target: QuickActionEntry, other: QuickActionEntry) => {
                    const targetKey = quickActionKey(target)
                    const otherKey = quickActionKey(other)
                    const without = entries.filter(
                      (e) => quickActionKey(e) !== targetKey && quickActionKey(e) !== otherKey,
                    )
                    if (entries.some((e) => quickActionKey(e) === targetKey)) {
                      settingsMutation.mutate(without)
                    } else {
                      if (without.length >= QUICK_ACTIONS_MAX) {
                        toast.error(t('character.quick_actions.max_reached', { max: QUICK_ACTIONS_MAX }))
                        return
                      }
                      settingsMutation.mutate([...without, target])
                    }
                  }
                  return (
                    <div key={a.id} className="flex items-center gap-2 px-3 py-2 rounded-xl border bg-dnd-surface border-dnd-border">
                      <span className="flex-1 min-w-0 truncate text-sm font-body text-dnd-text">{a.name}</span>
                      <Pressable
                        type="button"
                        onClick={() => toggleExclusive(actionEntry, counterEntry)}
                        pending={pendingToggleKey === quickActionKey(actionEntry)}
                        className={`px-2.5 py-1.5 rounded-lg border text-[11px] font-cinzel uppercase tracking-wide
                          ${actionPinned ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text-muted'}`}
                      >
                        {t('character.quick_actions.pin_as_action')}
                      </Pressable>
                      <Pressable
                        type="button"
                        onClick={() => toggleExclusive(counterEntry, actionEntry)}
                        pending={pendingToggleKey === quickActionKey(counterEntry)}
                        className={`px-2.5 py-1.5 rounded-lg border text-[11px] font-cinzel uppercase tracking-wide
                          ${counterPinned ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text-muted'}`}
                      >
                        {t('character.quick_actions.pin_as_counter')}
                      </Pressable>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {editorGroupsBottom.map(renderGroup)}
        </div>
      </Sheet>

      <UsesEditSheet
        open={counterEdit !== null}
        title={counterEdit
          ? `${t('character.abilities.set_uses_title')} · ${counterEdit.kind === 'ability' ? counterEdit.ability.name : counterEdit.item.name}`
          : t('character.abilities.set_uses_title')}
        value={counterEdit?.kind === 'ability' ? (counterEdit.ability.uses ?? 0) : (counterEdit?.item.quantity ?? 0)}
        max={counterEdit?.kind === 'ability' ? (counterEdit.ability.max_uses ?? null) : null}
        isPending={usesMutation.isPending || ammoMutation.isPending}
        onClose={() => setCounterEdit(null)}
        onSave={(n) => {
          if (!counterEdit) return
          const opts = { onSuccess: () => setCounterEdit(null) }
          if (counterEdit.kind === 'ability') usesMutation.mutate({ abilityId: counterEdit.ability.id, uses: n }, opts)
          else ammoMutation.mutate({ itemId: counterEdit.item.id, quantity: n }, opts)
        }}
      />

      {/* Risultati */}
      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          onClose={() => setAttackState(null)}
          inspirationAvailable={!!char.heroic_inspiration}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate(attackState.itemId)}
        />
      )}
      {saveState && (
        <RollResultModal
          result={saveState.result}
          title={`${t('character.saves.title')}: ${t(`character.stats.${saveState.ability}`)}`}
          onClose={() => setSaveState(null)}
          inspirationAvailable={!!char.heroic_inspiration}
          isRerolling={saveRerollMutation.isPending}
          wasRerolled={saveState.wasRerolled}
          onInspirationReroll={() => saveRerollMutation.mutate(saveState.ability)}
        />
      )}

      {castFlow.elements}

      <ConfirmSheet
        open={confirmLongRest}
        onClose={() => setConfirmLongRest(false)}
        title={t('character.quick_actions.confirm_long_rest_title')}
        body={t('character.quick_actions.confirm_long_rest_body')}
        confirmLabel={t('character.quick_actions.rest_long')}
        confirmVariant="primary"
        loading={restMutation.isPending}
        onConfirm={() => restMutation.mutate('long')}
      />

      {shortRestOpen && (
        <HitDiceModal
          classes={char.classes ?? []}
          onSpend={(classId, count) => hitDieMutation.mutate({ classId, count })}
          onConfirmRest={() => restMutation.mutate('short')}
          onClose={() => setShortRestOpen(false)}
          isPending={hitDieMutation.isPending}
          pendingClassId={hitDieMutation.isPending ? hitDieMutation.variables?.classId : undefined}
          restPending={restMutation.isPending}
        />
      )}

      <ConfirmSheet
        open={confirmHitDie !== null}
        onClose={() => setConfirmHitDie(null)}
        title={t('character.quick_actions.spend_hit_die_title')}
        body={confirmHitDie
          ? t('character.quick_actions.spend_hit_die_body', {
              cls: confirmHitDie.cls.class_name,
              die: confirmHitDie.cls.hit_die ?? 8,
              remaining: confirmHitDie.remaining,
            })
          : undefined}
        confirmLabel={t('character.quick_actions.spend_hit_die_title')}
        confirmVariant="primary"
        loading={hitDieMutation.isPending}
        onConfirm={() => confirmHitDie && hitDieMutation.mutate({ classId: confirmHitDie.cls.id, count: 1 })}
      />

      {hitDieResult && (
        <HitDiceResultDialog result={hitDieResult} onClose={() => setHitDieResult(null)} />
      )}
    </>
  )
}
