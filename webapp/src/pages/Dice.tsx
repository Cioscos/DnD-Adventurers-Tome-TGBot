import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { DiceRollResult } from '@/types'

const DICE = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'] as const

type InitiativeResult = {
  roll: number
  dexMod: number
  total: number
}

export default function Dice() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [count, setCount] = useState(1)
  const [lastResult, setLastResult] = useState<DiceRollResult | null>(null)
  const [initiativeResult, setInitiativeResult] = useState<InitiativeResult | null>(null)
  const [showClearConfirm, setShowClearConfirm] = useState(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const { data: history = [] } = useQuery({
    queryKey: ['dice-history', charId],
    queryFn: () => api.dice.history(charId),
  })

  const rollMutation = useMutation({
    mutationFn: ({ die }: { die: string }) => api.dice.roll(charId, count, die),
    onSuccess: (result) => {
      setLastResult(result)
      setInitiativeResult(null)
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const initiativeMutation = useMutation({
    mutationFn: () => api.dice.roll(charId, 1, 'd20'),
    onSuccess: (result) => {
      const dexScore = char?.ability_scores.find((s) => s.name === 'dexterity')
      const dexMod = dexScore?.modifier ?? 0
      setInitiativeResult({ roll: result.total, dexMod, total: result.total + dexMod })
      setLastResult(null)
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const clearHistoryMutation = useMutation({
    mutationFn: () => api.dice.clearHistory(charId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      setShowClearConfirm(false)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleRoll = (die: string) => rollMutation.mutate({ die })

  const dexMod = char?.ability_scores.find((s) => s.name === 'dexterity')?.modifier ?? 0
  const modLabel = dexMod >= 0 ? `+${dexMod}` : String(dexMod)

  return (
    <Layout title={t('character.dice.title')} backTo={`/char/${charId}`}>
      {/* Initiative button */}
      <button
        onClick={() => initiativeMutation.mutate()}
        disabled={initiativeMutation.isPending || rollMutation.isPending}
        className="w-full py-3 rounded-2xl font-bold text-base
                   bg-yellow-500/20 text-yellow-300 active:opacity-70
                   disabled:opacity-40 transition-opacity"
      >
        ⚔️ {t('character.dice.initiative')} (d20 {modLabel})
      </button>

      {/* Dice count selector */}
      <Card>
        <p className="text-sm text-[var(--tg-theme-hint-color)] mb-2">Numero di dadi</p>
        <div className="flex gap-2 flex-wrap">
          {[1, 2, 3, 4].map((n) => (
            <button
              key={n}
              onClick={() => setCount(n)}
              className={`px-4 py-2 rounded-xl font-bold transition-all
                ${count === n
                  ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                  : 'bg-white/10'}`}
            >
              {n}
            </button>
          ))}
        </div>
      </Card>

      {/* Dice buttons */}
      <div className="grid grid-cols-4 gap-2">
        {DICE.map((die) => (
          <button
            key={die}
            onClick={() => handleRoll(die)}
            disabled={rollMutation.isPending || initiativeMutation.isPending}
            className="py-4 rounded-2xl bg-[var(--tg-theme-secondary-bg-color)]
                       font-bold text-lg active:opacity-70 transition-opacity
                       disabled:opacity-40"
          >
            {die}
          </button>
        ))}
      </div>

      {/* Initiative result */}
      {initiativeResult && (
        <Card className="text-center">
          <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">⚔️ {t('character.dice.initiative')}</p>
          <p className="text-5xl font-bold mb-1">{initiativeResult.total}</p>
          <p className="text-sm text-[var(--tg-theme-hint-color)]">
            d20 ({initiativeResult.roll}) {initiativeResult.dexMod >= 0 ? '+' : ''}{initiativeResult.dexMod}
          </p>
        </Card>
      )}

      {/* Last dice result */}
      {lastResult && (
        <Card className="text-center">
          <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">
            {count > 1 ? `${count}${lastResult.notation}` : lastResult.notation}
          </p>
          <p className="text-5xl font-bold mb-1">{lastResult.total}</p>
          {lastResult.rolls.length > 1 && (
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              [{lastResult.rolls.join(' + ')}]
            </p>
          )}
          <button
            onClick={() => {
              haptic.light()
              api.dice.postToChat(charId, lastResult).catch(() => {})
            }}
            className="mt-3 px-4 py-2 rounded-xl bg-blue-500/20 text-blue-300 text-sm font-medium"
          >
            📤 {t('character.dice.send_to_chat')}
          </button>
        </Card>
      )}

      {/* History */}
      {history.length > 0 && (
        <div>
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-semibold text-sm text-[var(--tg-theme-hint-color)]">
              {t('character.dice.history')}
            </h3>
            <button
              onClick={() => setShowClearConfirm(true)}
              className="text-xs text-red-400 active:opacity-70"
            >
              {t('character.dice.clear')}
            </button>
          </div>
          <div className="space-y-1">
            {history.slice(0, 10).map((entry, i) => (
              <Card key={i} className="!p-2 flex justify-between items-center">
                <span className="text-sm text-[var(--tg-theme-hint-color)]">{entry.notation}</span>
                <span className="font-bold">{entry.total}</span>
                {entry.rolls.length > 1 && (
                  <span className="text-xs text-[var(--tg-theme-hint-color)]">
                    [{entry.rolls.join('+')}]
                  </span>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Clear history confirmation */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.dice.clear_confirm')}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => clearHistoryMutation.mutate()}
                disabled={clearHistoryMutation.isPending}
                className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
              >
                {t('common.confirm')}
              </button>
              <button
                onClick={() => setShowClearConfirm(false)}
                className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
              >
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
