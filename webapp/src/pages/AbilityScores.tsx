import { Fragment, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, m } from 'framer-motion'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { ease, stagger } from '@/styles/motion'
import type { AbilityScore } from '@/types'
import AbilityScoresSkeleton from '@/components/skeletons/AbilityScoresSkeleton'
import AbilityScoreEditModal from '@/components/character/AbilityScoreEditModal'
import AbilityScoreCard from '@/components/character/AbilityScoreCard'
import AbilityScoreDetail from '@/components/character/AbilityScoreDetail'

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
  const [expanded, setExpanded] = useState<string | null>(null)

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

  const ordered = [...char.ability_scores]
    .sort((a, b) => DND_ABILITY_ORDER.indexOf(a.name) - DND_ABILITY_ORDER.indexOf(b.name))
  const rows: AbilityScore[][] = []
  for (let i = 0; i < ordered.length; i += 2) rows.push(ordered.slice(i, i + 2))

  return (
    <Layout title={t('character.stats.title')} backTo={`/char/${charId}`} group="skills" page="stats">
      <Reveal.Stagger stagger={stagger.list} cap={12} className="grid grid-cols-2 gap-3">
        {rows.map((row) => {
          const expandedScore = row.find((s) => s.name === expanded)
          return (
            <Fragment key={row.map((s) => s.name).join('-')}>
              {row.map((score) => (
                <Reveal.Item key={score.name}>
                  <AbilityScoreCard
                    score={score}
                    expanded={expanded === score.name}
                    onToggle={() => setExpanded((p) => (p === score.name ? null : score.name))}
                    onEdit={() => setEditing(score.name)}
                  />
                </Reveal.Item>
              ))}
              <AnimatePresence initial={false}>
                {expandedScore && (
                  <m.div
                    key={`detail-${expandedScore.name}`}
                    className="col-span-2 overflow-hidden"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: ease.inkSpread }}
                  >
                    <AbilityScoreDetail score={expandedScore} />
                  </m.div>
                )}
              </AnimatePresence>
            </Fragment>
          )
        })}
      </Reveal.Stagger>

      {(() => {
        const score = editing ? char.ability_scores.find((s) => s.name === editing) : undefined
        return (
          <AbilityScoreEditModal
            open={editing !== null && score !== undefined}
            label={score ? t(`character.stats.${score.name}`, { defaultValue: score.name }) : ''}
            currentValue={score?.value ?? 0}
            saving={updateMutation.isPending}
            onClose={() => setEditing(null)}
            onSave={(value) => { if (score) handleSave(score.name, value) }}
          />
        )
      })()}
    </Layout>
  )
}
