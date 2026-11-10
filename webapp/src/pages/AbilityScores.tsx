import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, m } from 'framer-motion'
import { toast } from 'sonner'
import { api, ApiError } from '@/api/client'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { askRollOptions, canRerollInspiration, refreshAfterOptions } from '@/lib/rollOptions'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import Layout from '@/components/Layout'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { ease, stagger } from '@/styles/motion'
import AbilityScoresSkeleton from '@/components/skeletons/AbilityScoresSkeleton'
import AbilityScoreEditModal from '@/components/character/AbilityScoreEditModal'
import AbilityScoreCard from '@/components/character/AbilityScoreCard'
import AbilityScoreDetail from '@/components/character/AbilityScoreDetail'
import { notifyMutationError } from '@/lib/mutationError'

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
  const [rollState, setRollState] = useState<{ result: RollResult; ability: string; wasRerolled: boolean } | null>(null)
  const rollD20 = useD20Roll()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

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
      notifyMutationError()
    },
  })

  // Prova pura: modificatore, nessuna competenza; opzioni al tiro e ritiro con l'Ispirazione come per le abilità.
  const rollMutation = useMutation({
    mutationFn: async ({ ability, mode }: { ability: string; mode: RollMode }) => {
      const choice = await askRollOptions(charId, { roll: 'ability', ability })
      return { result: await api.characters.rollAbilityCheck(charId, ability, d20Arg(mode, await rollD20(mode), choice)), ability }
    },
    onSuccess: ({ result, ability }) => {
      refreshAfterOptions(qc, charId, result.option_result)
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      setRollState({ result: { ...result, description: undefined }, ability, wasRerolled: false })
      haptic.success()
    },
    onError: () => notifyMutationError(),
  })
  const rerollMutation = useMutation({
    mutationFn: async (ability: string) => {
      let die: number | undefined
      if (animate3d && !reducedMotion) die = (await dice.playAndCollect([{ kind: 'd20', count: 1 }]))[0]?.value
      return api.characters.rollAbilityCheck(charId, ability, die, true)
    },
    onSuccess: (result) => {
      setRollState((prev) => prev && { ...prev, result: { ...result, description: undefined }, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else haptic.error()
    },
  })

  const handleSave = (ability: string, value: number) => {
    if (updateMutation.isPending) return
    if (value < 1 || value > 30) return
    const s = char?.ability_scores.find((x) => x.name === ability)
    if ((s?.base_value ?? s?.value) === value) {
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

  return (
    <Layout title={t('character.stats.title')} backTo={`/char/${charId}`} group="skills" page="stats">
      <Reveal.Stagger stagger={stagger.list} cap={12} className="border-y border-dnd-border divide-y divide-dnd-border/60">
        {ordered.map((score) => (
          <Reveal.Item key={score.name}>
            <AbilityScoreCard
              score={score}
              expanded={expanded === score.name}
              onToggle={() => setExpanded((p) => (p === score.name ? null : score.name))}
              onEdit={() => setEditing(score.name)}
              onRoll={(mode) => rollMutation.mutate({ ability: score.name, mode })}
              rolling={rollMutation.isPending && rollMutation.variables?.ability === score.name}
            />
            <AnimatePresence initial={false}>
              {expanded === score.name && (
                <m.div
                  key={`detail-${score.name}`}
                  className="overflow-hidden"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease: ease.inkSpread }}
                >
                  <AbilityScoreDetail score={score} />
                </m.div>
              )}
            </AnimatePresence>
          </Reveal.Item>
        ))}
      </Reveal.Stagger>

      {(() => {
        const score = editing ? char.ability_scores.find((s) => s.name === editing) : undefined
        return (
          <AbilityScoreEditModal
            open={editing !== null && score !== undefined}
            label={score ? t(`character.stats.${score.name}`, { defaultValue: score.name }) : ''}
            // Il PATCH salva il valore base: partire dall'effettivo (con i bonus degli oggetti) li sommerebbe due volte.
            currentValue={score?.base_value ?? score?.value ?? 0}
            effectiveValue={score?.value}
            saving={updateMutation.isPending}
            onClose={() => setEditing(null)}
            onSave={(value) => { if (score) handleSave(score.name, value) }}
          />
        )
      })()}

      {rollState && (
        <RollResultModal
          result={rollState.result}
          title={`${t('character.stats.check_title')}: ${t(`character.stats.${rollState.ability}`)}`}
          inspirationAvailable={canRerollInspiration(char)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.ability)}
          afterRoll={{ charId, query: { roll: 'ability', ability: rollState.ability } }}
          noCritical
          onClose={() => setRollState(null)}
        />
      )}
    </Layout>
  )
}
