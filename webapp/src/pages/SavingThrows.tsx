import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']

function profBonus(level: number) {
  return Math.floor((level - 1) / 4) + 2
}

export default function SavingThrows() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [rollResult, setRollResult] = useState<{ result: RollResult; title: string } | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: (saving_throws: Record<string, boolean>) =>
      api.characters.updateSavingThrows(charId, saving_throws),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const rollMutation = useMutation({
    mutationFn: (ability: string) => api.characters.rollSavingThrow(charId, ability),
    onSuccess: (result, ability) => {
      setRollResult({
        result,
        title: `${t('character.saves.title')} — ${t(`character.stats.${ability}`)}`,
      })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const saves: Record<string, boolean> = (char.saving_throws as Record<string, boolean>) ?? {}
  const pb = profBonus(char.total_level || 1)

  const toggle = (ability: string) => {
    const current = saves[ability] ?? false
    mutation.mutate({ ...saves, [ability]: !current })
  }

  return (
    <Layout title={t('character.saves.title')} backTo={`/char/${charId}`} group="combat" page="saves">
      <Card variant="elevated">
        <p className="text-sm text-dnd-text-secondary">
          {t('character.skills.prof_bonus')}: <span className="font-bold text-white">+{pb}</span>
        </p>
      </Card>

      <div className="space-y-1">
        {ABILITIES.map((ability) => {
          const isProficient = saves[ability] ?? false
          const score = char.ability_scores.find((s) => s.name === ability)
          const abilMod = score?.modifier ?? 0
          const total = abilMod + (isProficient ? pb : 0)

          return (
            <div
              key={ability}
              className="flex items-center gap-3 px-4 py-3 rounded-xl
                         bg-dnd-surface"
            >
              {/* Proficiency toggle */}
              <button
                onClick={() => toggle(ability)}
                className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0
                  ${isProficient ? 'bg-dnd-gold border-dnd-gold' : 'border-white/30'}`}
              >
                {isProficient && <span className="text-xs text-white font-bold">✓</span>}
              </button>

              {/* Name */}
              <button
                onClick={() => toggle(ability)}
                className="flex-1 text-left font-medium active:opacity-70"
              >
                {t(`character.stats.${ability}`)}
              </button>

              {/* Bonus */}
              <span className={`text-sm font-bold w-8 text-right ${total >= 0 ? 'text-[#2ecc71]' : 'text-[var(--dnd-danger)]'}`}>
                {total >= 0 ? '+' : ''}{total}
              </span>

              {/* Roll button */}
              <button
                onClick={() => rollMutation.mutate(ability)}
                disabled={rollMutation.isPending}
                className="text-lg leading-none shrink-0 active:opacity-60 disabled:opacity-30"
                title={t('character.saves.roll')}
              >
                🎲
              </button>
            </div>
          )
        })}
      </div>

      {rollResult && (
        <RollResultModal
          result={rollResult.result}
          title={rollResult.title}
          onClose={() => setRollResult(null)}
        />
      )}
    </Layout>
  )
}
