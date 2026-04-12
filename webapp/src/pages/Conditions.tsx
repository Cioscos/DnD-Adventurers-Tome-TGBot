import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

const CONDITIONS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified',
  'poisoned', 'prone', 'restrained', 'stunned', 'unconscious',
]

const CONDITION_EMOJIS: Record<string, string> = {
  blinded: '👁️', charmed: '💕', deafened: '🔇', frightened: '😱',
  grappled: '🤝', incapacitated: '💫', invisible: '👻', paralyzed: '⚡',
  petrified: '🗿', poisoned: '🤢', prone: '⬇️', restrained: '⛓️',
  stunned: '😵', unconscious: '💤',
}

export default function Conditions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [exhaustionLevel, setExhaustionLevel] = useState<number | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  useEffect(() => {
    if (char && exhaustionLevel === null) {
      const conds = (char.conditions as Record<string, unknown>) ?? {}
      if (typeof conds['exhaustion'] === 'number') {
        setExhaustionLevel(conds['exhaustion'] as number)
      }
    }
  }, [char])

  const mutation = useMutation({
    mutationFn: (conditions: Record<string, unknown>) =>
      api.characters.updateConditions(charId, conditions),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const conditions: Record<string, unknown> = (char.conditions as Record<string, unknown>) ?? {}
  const currentExhaustion = typeof conditions['exhaustion'] === 'number'
    ? (conditions['exhaustion'] as number)
    : 0

  const toggle = (key: string) => {
    const current = conditions[key] ?? false
    mutation.mutate({ ...conditions, [key]: !current })
  }

  const setExhaustion = (level: number) => {
    setExhaustionLevel(level)
    mutation.mutate({ ...conditions, exhaustion: level })
  }

  const activeCount = CONDITIONS.filter((c) => conditions[c]).length + (currentExhaustion > 0 ? 1 : 0)

  return (
    <Layout title={t('character.conditions.title')} backTo={`/char/${charId}`}>
      {activeCount === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">
            {t('character.conditions.none_active')}
          </p>
        </Card>
      )}

      {/* Exhaustion */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="font-medium">🥵 {t('character.conditions.exhaustion_condition')}</span>
          <span className={`text-lg font-bold ${currentExhaustion > 0 ? 'text-orange-400' : 'text-[var(--tg-theme-hint-color)]'}`}>
            {currentExhaustion}/6
          </span>
        </div>
        <div className="flex gap-2">
          {[0, 1, 2, 3, 4, 5, 6].map((level) => (
            <button
              key={level}
              onClick={() => setExhaustion(level)}
              className={`flex-1 py-1.5 rounded-lg text-sm font-bold transition-all
                ${(exhaustionLevel ?? currentExhaustion) === level
                  ? 'bg-orange-500 text-white'
                  : 'bg-white/10 text-[var(--tg-theme-hint-color)]'}`}
            >
              {level}
            </button>
          ))}
        </div>
      </Card>

      {/* Condition grid */}
      <div className="grid grid-cols-2 gap-2">
        {CONDITIONS.map((cond) => {
          const active = !!conditions[cond]
          return (
            <button
              key={cond}
              onClick={() => toggle(cond)}
              className={`flex items-center gap-2 px-3 py-3 rounded-xl text-left transition-all
                ${active
                  ? 'bg-red-500/30 border border-red-500/60 text-white'
                  : 'bg-[var(--tg-theme-secondary-bg-color)] border border-transparent'}`}
            >
              <span className="text-xl">{CONDITION_EMOJIS[cond]}</span>
              <span className="text-sm font-medium leading-tight">
                {t(`character.conditions.${cond}`)}
              </span>
            </button>
          )
        })}
      </div>
    </Layout>
  )
}
