import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic, sendDiceResultToChat } from '@/auth/telegram'
import type { DiceRollResult } from '@/types'

const DICE = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'] as const

export default function Dice() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [count, setCount] = useState(1)
  const [lastResult, setLastResult] = useState<DiceRollResult | null>(null)

  const { data: history = [] } = useQuery({
    queryKey: ['dice-history', charId],
    queryFn: () => api.dice.history(charId),
  })

  const rollMutation = useMutation({
    mutationFn: ({ die }: { die: string }) => api.dice.roll(charId, count, die),
    onSuccess: (result) => {
      setLastResult(result)
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const handleRoll = (die: string) => rollMutation.mutate({ die })

  return (
    <Layout title={t('character.dice.title')} backTo={`/char/${charId}`}>
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
            disabled={rollMutation.isPending}
            className="py-4 rounded-2xl bg-[var(--tg-theme-secondary-bg-color)]
                       font-bold text-lg active:opacity-70 transition-opacity
                       disabled:opacity-40"
          >
            {die}
          </button>
        ))}
      </div>

      {/* Last result */}
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
            onClick={() => sendDiceResultToChat(lastResult)}
            className="mt-3 px-4 py-2 rounded-xl bg-blue-500/20 text-blue-300 text-sm font-medium"
          >
            📤 {t('character.dice.send_to_chat')}
          </button>
        </Card>
      )}

      {/* History */}
      {history.length > 0 && (
        <div>
          <h3 className="font-semibold mb-2 text-sm text-[var(--tg-theme-hint-color)]">
            {t('character.dice.history')}
          </h3>
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
    </Layout>
  )
}
