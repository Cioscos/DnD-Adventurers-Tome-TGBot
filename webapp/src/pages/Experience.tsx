import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import { haptic } from '@/auth/telegram'

const XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]

function levelFromXp(xp: number) {
  let level = 1
  for (let i = 1; i < XP_THRESHOLDS.length; i++) {
    if (xp >= XP_THRESHOLDS[i]) level = i + 1
    else break
  }
  return Math.min(level, 20)
}

export default function Experience() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [addValue, setAddValue] = useState('')
  const [setMode, setSetMode] = useState(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: ({ add, set }: { add?: number; set?: number }) =>
      api.characters.updateXP(charId, { add, set }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setAddValue('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const xp = char.experience_points
  const level = levelFromXp(xp)
  const nextThreshold = XP_THRESHOLDS[level] ?? null
  const prevThreshold = XP_THRESHOLDS[level - 1] ?? 0
  const progress = nextThreshold
    ? Math.round(((xp - prevThreshold) / (nextThreshold - prevThreshold)) * 100)
    : 100
  const xpToNext = nextThreshold ? nextThreshold - xp : 0

  const totalClassLevel = (char.classes ?? []).reduce((s: number, c: { level: number }) => s + c.level, 0)
  const isSingleClass = (char.classes ?? []).length === 1
  const isMulticlass = (char.classes ?? []).length > 1
  const levelUpAvailable = isMulticlass && level > totalClassLevel

  const handleApply = () => {
    const n = parseInt(addValue, 10)
    if (isNaN(n)) return
    mutation.mutate(setMode ? { set: n } : { add: n })
  }

  const quickAmounts = [50, 100, 200, 500]

  return (
    <Layout title={t('character.xp.title')} backTo={`/char/${charId}`} group="character" page="xp">
      {/* Level-up notification for multiclass characters */}
      {levelUpAvailable && (
        <div className="rounded-2xl bg-[var(--dnd-gold-glow)] border border-dnd-gold-dim/40 px-4 py-3 text-sm text-dnd-gold">
          {t('character.xp.level_up_available')}
        </div>
      )}

      {/* Info for single-class characters */}
      {isSingleClass && (
        <p className="text-xs text-dnd-text-secondary text-center px-2">
          {t('character.xp.single_class_synced')}
        </p>
      )}

      <Card variant="elevated">
        <div className="text-center">
          <p className="text-sm text-dnd-text-secondary mb-1">
            {t('character.xp.level', { level })}
          </p>
          <p className="text-5xl font-bold text-dnd-gold">{xp.toLocaleString()}</p>
          <p className="text-sm text-dnd-text-secondary mt-1">{t('character.xp.current')}</p>
        </div>

        {nextThreshold && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-dnd-text-secondary mb-1">
              <span>Liv. {level}</span>
              <span>{xpToNext.toLocaleString()} XP al Liv. {level + 1}</span>
            </div>
            <div className="w-full bg-dnd-surface rounded-full h-2">
              <div
                className="bg-dnd-gold h-2 rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-right text-dnd-text-secondary mt-1">{progress}%</p>
          </div>
        )}
      </Card>

      {/* Mode toggle */}
      <div className="flex gap-2">
        <DndButton
          variant={!setMode ? 'primary' : 'secondary'}
          onClick={() => setSetMode(false)}
          className="flex-1"
        >
          + {t('character.xp.add')}
        </DndButton>
        <DndButton
          variant={setMode ? 'primary' : 'secondary'}
          onClick={() => setSetMode(true)}
          className="flex-1"
        >
          = Imposta
        </DndButton>
      </div>

      <Card>
        <div className="flex gap-3">
          <DndInput
            type="number"
            min={0}
            value={addValue}
            onChange={setAddValue}
            placeholder="XP"
            className="flex-1"
          />
          <DndButton
            onClick={handleApply}
            disabled={!addValue}
            loading={mutation.isPending}
            className="px-5"
          >
            &#x2713;
          </DndButton>
        </div>
      </Card>

      <div className="grid grid-cols-4 gap-2">
        {quickAmounts.map((n) => (
          <DndButton
            key={n}
            variant="secondary"
            onClick={() => mutation.mutate({ add: n })}
            className="py-2"
          >
            +{n}
          </DndButton>
        ))}
      </div>
    </Layout>
  )
}
