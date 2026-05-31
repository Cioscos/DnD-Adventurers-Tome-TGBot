import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import type { AbilityScore } from '@/types'
import AbilityScoresSkeleton from '@/components/skeletons/AbilityScoresSkeleton'
import AbilityScoreEditModal from '@/components/character/AbilityScoreEditModal'

// Canonical D&D 5e ordering — STR/DEX/CON/INT/WIS/CHA (mirror HeroScreen.tsx).
const DND_ABILITY_ORDER = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
]

export default function AbilityScores() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [editing, setEditing] = useState<string | null>(null)

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
    },
    onError: () => {
      haptic.error()
    },
  })

  const handleSave = (ability: string, value: number) => {
    if (updateMutation.isPending) return
    if (value < 1 || value > 30) return
    if (char?.ability_scores.find((s) => s.name === ability)?.value === value) {
      setEditing(null)
      return
    }
    updateMutation.mutate({ ability, value })
  }

  if (!char) {
    return (
      <Layout title={t('character.stats.title')} backTo={`/char/${charId}`} group="skills" page="stats">
        <AbilityScoresSkeleton />
      </Layout>
    )
  }

  return (
    <Layout title={t('character.stats.title')} backTo={`/char/${charId}`} group="skills" page="stats">
      <Reveal.Stagger stagger={stagger.list} className="grid grid-cols-2 gap-3">
        {[...char.ability_scores]
          .sort((a, b) => DND_ABILITY_ORDER.indexOf(a.name) - DND_ABILITY_ORDER.indexOf(b.name))
          .map((score: AbilityScore) => {

          return (
            <Reveal.Item key={score.name}>
              <Surface
                variant="elevated"
                ornamented
                className="relative overflow-hidden"
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
                  <m.button
                    onClick={() => setEditing(score.name)}
                    className="shrink-0 w-11 h-11 rounded-full bg-dnd-surface-raised border border-dnd-border flex items-center justify-center text-dnd-gold"
                    whileTap={{ scale: 0.9 }}
                    aria-label={t('common.edit')}
                  >
                    <Pencil size={14} />
                  </m.button>
                </div>

                <m.div
                  key="view"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="flex items-end gap-2"
                  transition={spring.snappy}
                >
                  <span className="text-4xl font-mono font-bold leading-none tabular-nums text-dnd-text"
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

      {editing && (() => {
        const score = char.ability_scores.find((s) => s.name === editing)
        if (!score) return null
        return (
          <AbilityScoreEditModal
            open={!!editing}
            label={t(`character.stats.${score.name}`, { defaultValue: score.name })}
            currentValue={score.value}
            saving={updateMutation.isPending}
            onClose={() => setEditing(null)}
            onSave={(value) => handleSave(score.name, value)}
          />
        )
      })()}
    </Layout>
  )
}
