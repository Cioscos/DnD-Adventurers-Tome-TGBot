import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, Check } from 'lucide-react'
import {
  GiCrossedSwords, GiShieldEchoes, GiSpellBook, GiLightningStorm,
} from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Sheet from '@/components/ui/Sheet'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'
import { haptic } from '@/auth/telegram'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useToast } from '@/hooks/useToast'
import {
  readQuickActions,
  resolveQuickActions,
  quickActionKey,
  QUICK_ACTIONS_MAX,
  SAVE_ABILITIES,
  type QuickActionEntry,
  type ResolvedQuickAction,
} from '@/lib/quickActions'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

type AttackState = { result: WeaponAttackResult; itemId: number; wasRerolled: boolean }
type SaveRollState = { result: RollResult; ability: string; wasRerolled: boolean }

const TYPE_ICONS = {
  weapon: GiCrossedSwords,
  save: GiShieldEchoes,
  spell: GiSpellBook,
} as const

export default function QuickActions({ char }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

  const [editorOpen, setEditorOpen] = useState(false)
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const [saveState, setSaveState] = useState<SaveRollState | null>(null)

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

  const run = (action: ResolvedQuickAction) => {
    haptic.light()
    if (action.type === 'weapon') {
      attackMutation.mutate(action.item.id)
    } else if (action.type === 'save') {
      saveMutation.mutate(action.ability)
    } else {
      navigate(`/char/${char.id}/spells?focus=${action.spell.id}`)
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

  const actionLabel = (a: ResolvedQuickAction): string =>
    a.type === 'weapon' ? a.item.name
      : a.type === 'save' ? t(`character.stats.${a.ability}`)
        : a.spell.name

  const weapons = (char.items ?? []).filter((i) => i.item_type === 'weapon')
  const spells = char.spells ?? []
  const busy = attackMutation.isPending || saveMutation.isPending

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
          <m.button
            type="button"
            onClick={() => { haptic.light(); setEditorOpen(true) }}
            whileTap={{ scale: 0.9 }}
            aria-label={t('character.quick_actions.edit')}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/40 text-dnd-gold-bright"
          >
            <Plus size={16} />
          </m.button>
        </div>

        {resolved.length === 0 ? (
          <p className="text-xs text-dnd-text-muted font-body italic">
            {t('character.quick_actions.empty_hint')}
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {resolved.map((a, i) => {
              const Icon = TYPE_ICONS[a.type]
              const spanFull = resolved.length % 2 === 1 && i === resolved.length - 1
              return (
                <m.button
                  key={a.key}
                  type="button"
                  disabled={busy}
                  onClick={() => run(a)}
                  whileTap={{ scale: 0.96 }}
                  className={`min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl
                              bg-dnd-surface border border-dnd-border text-left
                              disabled:opacity-60 ${spanFull ? 'col-span-2' : ''}`}
                >
                  <Icon size={16} className="text-dnd-gold shrink-0" />
                  <span className="flex-1 min-w-0 truncate text-sm text-dnd-text font-body">
                    {actionLabel(a)}
                  </span>
                </m.button>
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

          {([
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
          ]).map((group) => (
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
                      <button
                        key={quickActionKey(entry)}
                        type="button"
                        onClick={() => toggleEntry(entry)}
                        className={`w-full min-h-[44px] flex items-center gap-2 px-3 py-2 rounded-xl border text-left
                          ${pinned
                            ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright'
                            : 'bg-dnd-surface border-dnd-border text-dnd-text'}`}
                      >
                        <span className="flex-1 min-w-0 truncate text-sm font-body">{label}</span>
                        {pinned && <Check size={16} className="shrink-0" />}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      </Sheet>

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
    </>
  )
}
