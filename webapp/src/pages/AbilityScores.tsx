import { useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Pencil, Check, X } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import type { AbilityScore } from '@/types'

const ABILITY_THEME: Record<string, string> = {
  strength: 'from-[var(--dnd-crimson-deep)]/40 via-dnd-surface to-dnd-surface border-dnd-crimson/40 text-[var(--dnd-crimson-bright)]',
  dexterity: 'from-[var(--dnd-emerald-deep)]/40 via-dnd-surface to-dnd-surface border-dnd-emerald/40 text-[var(--dnd-emerald-bright)]',
  constitution: 'from-[var(--dnd-amber)]/20 via-dnd-surface to-dnd-surface border-dnd-amber/40 text-[var(--dnd-amber)]',
  intelligence: 'from-[var(--dnd-cobalt)]/20 via-dnd-surface to-dnd-surface border-dnd-cobalt/40 text-[var(--dnd-cobalt-bright)]',
  wisdom: 'from-[var(--dnd-arcane-deep)]/40 via-dnd-surface to-dnd-surface border-dnd-arcane/40 text-dnd-arcane-bright',
  charisma: 'from-[var(--dnd-gold-deep)]/40 via-dnd-surface to-dnd-surface border-dnd-gold/40 text-dnd-gold-bright',
}

export default function AbilityScores() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [editing, setEditing] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  // Synchronous guard against double-fire of handleSave (Input.onCommit + button.onClick
  // can both fire when the user taps Salva — `updateMutation.isPending` isn't yet true
  // at the second call, so we need a ref that flips immediately.
  const savingRef = useRef(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const updateMutation = useMutation({
    mutationFn: ({ ability, value }: { ability: string; value: number }) =>
      api.characters.updateAbilityScore(charId, ability, value),
    onSuccess: (updated, vars) => {
      const oldHpMax = char?.hit_points ?? null
      qc.setQueryData(['character', charId], updated)
      setEditing(null)
      haptic.success()
      if (vars.ability === 'constitution' && oldHpMax !== null && updated.hit_points !== oldHpMax) {
        toast.success(t('character.stats.hp_recalc_toast', {
          old: oldHpMax,
          new: updated.hit_points,
        }))
      }
      savingRef.current = false
    },
    onError: () => {
      haptic.error()
      savingRef.current = false
    },
  })

  const handleSave = (ability: string) => {
    if (savingRef.current || updateMutation.isPending) return
    const n = parseInt(editValue, 10)
    if (isNaN(n) || n < 1 || n > 30) return
    if (char?.ability_scores.find((s) => s.name === ability)?.value === n) {
      setEditing(null)
      return
    }
    savingRef.current = true
    updateMutation.mutate({ ability, value: n })
  }

  if (!char) return null

  return (
    <Layout title={t('character.stats.title')} backTo={`/char/${charId}`} group="skills" page="stats">
      <Reveal.Stagger stagger={stagger.list} className="grid grid-cols-2 gap-3">
        {char.ability_scores.map((score: AbilityScore) => {
          const theme = ABILITY_THEME[score.name] ?? ABILITY_THEME.charisma
          const isEditing = editing === score.name

          return (
            <Reveal.Item key={score.name}>
              <Surface
                variant="elevated"
                ornamented
                className={`relative overflow-hidden bg-gradient-to-br ${theme}`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span
                    className="min-w-0 text-[11px] font-cinzel uppercase tracking-[0.15em] leading-tight opacity-85"
                    title={t(`character.stats.${score.name}`, { defaultValue: score.name })}
                  >
                    {t(`character.ability.${score.name}_short`, {
                      defaultValue: t(`character.stats.${score.name}`, { defaultValue: score.name }),
                    })}
                  </span>
                  {!isEditing && (
                    <m.button
                      onClick={() => {
                        setEditing(score.name)
                        setEditValue(String(score.value))
                      }}
                      className="shrink-0 w-11 h-11 rounded-full bg-dnd-surface-raised border border-dnd-border flex items-center justify-center text-dnd-gold"
                      whileTap={{ scale: 0.9 }}
                      aria-label={t('common.edit')}
                    >
                      <Pencil size={14} />
                    </m.button>
                  )}
                </div>

                <AnimatePresence mode="wait" initial={false}>
                  {isEditing ? (
                    <m.div
                      key="edit"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex gap-1.5 items-center"
                    >
                      <div className="flex-1">
                        <Input
                          value={editValue}
                          onChange={setEditValue}
                          type="number"
                          min={1}
                          max={30}
                          inputMode="numeric"
                          autoFocus
                          onCommit={() => handleSave(score.name)}
                          className="[&_input]:text-2xl [&_input]:font-display [&_input]:font-black [&_input]:text-center [&_input]:min-h-[56px]"
                        />
                      </div>
                      <m.button
                        onClick={() => handleSave(score.name)}
                        className="shrink-0 w-11 h-11 rounded-lg bg-[var(--dnd-emerald)]/20 text-[var(--dnd-emerald-bright)] border border-dnd-emerald/40 flex items-center justify-center"
                        whileTap={{ scale: 0.9 }}
                        aria-label={t('common.save')}
                      >
                        <Check size={18} />
                      </m.button>
                      <m.button
                        onClick={() => setEditing(null)}
                        className="shrink-0 w-11 h-11 rounded-lg bg-[var(--dnd-crimson)]/15 text-[var(--dnd-crimson-bright)] border border-[var(--dnd-crimson)]/40 flex items-center justify-center"
                        whileTap={{ scale: 0.9 }}
                        aria-label={t('common.cancel')}
                      >
                        <X size={18} />
                      </m.button>
                    </m.div>
                  ) : (
                    <m.div
                      key="view"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="flex items-end gap-2"
                      transition={spring.snappy}
                    >
                      <span className="text-5xl font-display font-black leading-none tabular-nums"
                            style={{ textShadow: '0 2px 6px rgba(0,0,0,0.6)' }}>
                        {score.value}
                      </span>
                      <div className="flex flex-col items-center mb-1">
                        <span className="text-[9px] font-cinzel uppercase tracking-widest opacity-60 leading-none">
                          {t('character.ability.mod_label')}
                        </span>
                        <span className="text-base font-mono font-bold tabular-nums px-2 py-0.5 rounded-full bg-black/25 mt-0.5">
                          {score.modifier >= 0 ? '+' : ''}{score.modifier}
                        </span>
                      </div>
                    </m.div>
                  )}
                </AnimatePresence>

                {score.modifiers_applied && score.modifiers_applied.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-dnd-border/50 space-y-1 text-[11px] font-body">
                    <p className="text-[9px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
                      {t('character.ability.sources')}
                    </p>
                    <div className="flex items-center justify-between text-dnd-text-faint">
                      <span>{t('character.ability.breakdown.base')}</span>
                      <span className="font-mono">{score.base_value ?? score.value}</span>
                    </div>
                    {score.modifiers_applied.map((mod, idx) => (
                      <div key={idx} className="flex items-center justify-between text-dnd-gold-dim">
                        <span className="truncate flex-1">{mod.source}</span>
                        <span className="font-mono shrink-0 ml-2">
                          {mod.kind === 'relative'
                            ? (mod.value >= 0 ? `+${mod.value}` : mod.value)
                            : `=${mod.value}`}
                        </span>
                      </div>
                    ))}
                    <div className="flex items-center justify-between text-dnd-gold-bright font-bold">
                      <span>{t('character.ability.breakdown.effective')}</span>
                      <span className="font-mono">{score.value}</span>
                    </div>
                  </div>
                )}
              </Surface>
            </Reveal.Item>
          )
        })}
      </Reveal.Stagger>
    </Layout>
  )
}
