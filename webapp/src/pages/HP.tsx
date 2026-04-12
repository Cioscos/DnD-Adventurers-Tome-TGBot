import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import HPBar from '@/components/HPBar'
import { haptic } from '@/auth/telegram'

type HPOp = 'damage' | 'heal' | 'set_max' | 'set_current' | 'set_temp'

export default function HP() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [value, setValue] = useState('')
  const [activeOp, setActiveOp] = useState<HPOp>('damage')


  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const hpMutation = useMutation({
    mutationFn: ({ op, val }: { op: HPOp; val: number }) =>
      api.characters.updateHp(charId, op, val),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setValue('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const restMutation = useMutation({
    mutationFn: (restType: 'long' | 'short') =>
      api.characters.rest(charId, restType),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const deathMutation = useMutation({
    mutationFn: (action: string) =>
      api.characters.updateDeathSaves(charId, action),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const handleApply = () => {
    const n = parseInt(value, 10)
    if (isNaN(n) || n <= 0) return
    hpMutation.mutate({ op: activeOp, val: n })
  }

  if (!char) return null

  const ds = char.death_saves ?? { successes: 0, failures: 0, stable: false }
  const isDying = char.current_hit_points === 0 && !ds.stable

  const ops: { key: HPOp; label: string; color: string }[] = [
    { key: 'damage',      label: t('character.hp.damage'),      color: 'bg-red-500/80' },
    { key: 'heal',        label: t('character.hp.heal'),         color: 'bg-green-500/80' },
    { key: 'set_current', label: t('character.hp.set_current'),  color: 'bg-blue-500/80' },
    { key: 'set_max',     label: t('character.hp.set_max'),      color: 'bg-orange-500/80' },
    { key: 'set_temp',    label: t('character.hp.set_temp'),     color: 'bg-cyan-500/80' },
  ]

  return (
    <Layout title={t('character.hp.title')} backTo={`/char/${charId}`}>
      {/* HP display */}
      <Card>
        <div className="flex justify-between items-start mb-3">
          <div>
            <p className="text-4xl font-bold">
              {char.current_hit_points}
              <span className="text-xl text-[var(--tg-theme-hint-color)]">/{char.hit_points}</span>
            </p>
            {char.temp_hp > 0 && (
              <p className="text-sm text-blue-400">+{char.temp_hp} temporanei</p>
            )}
          </div>
          <div className="text-right text-sm text-[var(--tg-theme-hint-color)]">
            <p>{t('character.hp.max')}: {char.hit_points}</p>
            {char.temp_hp > 0 && <p>{t('character.hp.temp')}: {char.temp_hp}</p>}
          </div>
        </div>
        <HPBar current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} />
      </Card>

      {/* Op selector */}
      <div className="flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
        {ops.map((op) => (
          <button
            key={op.key}
            onClick={() => setActiveOp(op.key)}
            className={`shrink-0 px-3 py-1.5 rounded-xl text-sm font-medium transition-all
              ${activeOp === op.key ? op.color + ' text-white' : 'bg-white/10'}`}
          >
            {op.label}
          </button>
        ))}
      </div>

      {/* Number input */}
      <Card>
        <div className="flex gap-3 items-center">
          <input
            type="number"
            min="0"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleApply()}
            placeholder="0"
            className="flex-1 bg-white/10 rounded-xl px-3 py-3 text-xl font-bold text-center
                       outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
          />
          <button
            onClick={handleApply}
            disabled={!value || hpMutation.isPending}
            className="px-5 py-3 rounded-xl bg-[var(--tg-theme-button-color)]
                       text-[var(--tg-theme-button-text-color)] font-semibold
                       disabled:opacity-40 active:opacity-80"
          >
            {hpMutation.isPending ? '...' : '✓'}
          </button>
        </div>
      </Card>

      {/* Quick heal / damage shortcuts */}
      <div className="grid grid-cols-4 gap-2">
        {[1, 5, 10, 20].map((n) => (
          <button
            key={n}
            onClick={() => {
              hpMutation.mutate({ op: activeOp, val: n })
              haptic.light()
            }}
            className="py-2 rounded-xl bg-white/10 text-sm font-medium active:opacity-70"
          >
            {activeOp === 'damage' ? `-${n}` : activeOp === 'heal' ? `+${n}` : String(n)}
          </button>
        ))}
      </div>

      {/* Rest buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => restMutation.mutate('short')}
          disabled={restMutation.isPending}
          className="py-3 rounded-2xl bg-blue-500/20 text-blue-300 font-medium active:opacity-70"
        >
          🌙 Riposo breve
        </button>
        <button
          onClick={() => restMutation.mutate('long')}
          disabled={restMutation.isPending}
          className="py-3 rounded-2xl bg-purple-500/20 text-purple-300 font-medium active:opacity-70"
        >
          💤 Riposo lungo
        </button>
      </div>

      {/* Death saves (shown when HP = 0) */}
      {isDying && (
        <Card>
          <h3 className="font-semibold mb-3">💀 {t('character.death_saves.title')}</h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="text-center">
              <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">
                {t('character.death_saves.successes')}
              </p>
              <div className="flex justify-center gap-2">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className={`w-6 h-6 rounded-full border-2 ${
                      i < (ds.successes ?? 0)
                        ? 'bg-green-500 border-green-500'
                        : 'border-white/30'
                    }`}
                  />
                ))}
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">
                {t('character.death_saves.failures')}
              </p>
              <div className="flex justify-center gap-2">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className={`w-6 h-6 rounded-full border-2 ${
                      i < (ds.failures ?? 0)
                        ? 'bg-red-500 border-red-500'
                        : 'border-white/30'
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => deathMutation.mutate('success')}
              className="py-2 rounded-xl bg-green-500/20 text-green-300 text-sm font-medium"
            >
              ✓ {t('character.death_saves.success')}
            </button>
            <button
              onClick={() => deathMutation.mutate('failure')}
              className="py-2 rounded-xl bg-red-500/20 text-red-300 text-sm font-medium"
            >
              ✗ {t('character.death_saves.failure')}
            </button>
            <button
              onClick={() => deathMutation.mutate('stabilize')}
              className="py-2 rounded-xl bg-blue-500/20 text-blue-300 text-sm font-medium"
            >
              💊 {t('character.death_saves.stabilize')}
            </button>
          </div>
          <button
            onClick={() => deathMutation.mutate('reset')}
            className="w-full mt-2 py-2 rounded-xl bg-white/10 text-sm"
          >
            {t('character.death_saves.reset')}
          </button>
        </Card>
      )}
    </Layout>
  )
}
