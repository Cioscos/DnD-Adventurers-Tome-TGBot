import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { AbilityScore } from '@/types'

const ABILITY_LABELS: Record<string, string> = {
  strength: '💪',
  dexterity: '🤸',
  constitution: '🏋️',
  intelligence: '🧠',
  wisdom: '🦉',
  charisma: '✨',
}

export default function AbilityScores() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [editing, setEditing] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const updateMutation = useMutation({
    mutationFn: ({ ability, value }: { ability: string; value: number }) =>
      api.characters.updateAbilityScore(charId, ability, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setEditing(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleSave = (ability: string) => {
    const n = parseInt(editValue, 10)
    if (isNaN(n) || n < 1 || n > 30) return
    updateMutation.mutate({ ability, value: n })
  }

  if (!char) return null

  return (
    <Layout title={t('character.stats.title')} backTo={`/char/${charId}`}>
      <div className="grid grid-cols-2 gap-3">
        {char.ability_scores.map((score: AbilityScore) => (
          <Card key={score.name}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium">
                {ABILITY_LABELS[score.name] ?? '—'}{' '}
                {t(`character.stats.${score.name}`, { defaultValue: score.name })}
              </span>
              <button
                onClick={() => {
                  setEditing(score.name)
                  setEditValue(String(score.value))
                }}
                className="text-xs text-[var(--tg-theme-link-color)]"
              >
                {t('common.edit')}
              </button>
            </div>

            {editing === score.name ? (
              <div className="flex gap-2 items-center mt-1">
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSave(score.name)
                    if (e.key === 'Escape') setEditing(null)
                  }}
                  autoFocus
                  className="w-16 bg-white/10 rounded-lg px-2 py-1 text-center text-lg font-bold
                             outline-none focus:ring-1 focus:ring-[var(--tg-theme-button-color)]"
                />
                <button
                  onClick={() => handleSave(score.name)}
                  className="text-green-400 font-bold"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditing(null)}
                  className="text-red-400"
                >
                  ✗
                </button>
              </div>
            ) : (
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold">{score.value}</span>
                <span className="text-lg text-[var(--tg-theme-hint-color)] mb-1">
                  {score.modifier >= 0 ? '+' : ''}{score.modifier}
                </span>
              </div>
            )}
          </Card>
        ))}
      </div>
    </Layout>
  )
}
