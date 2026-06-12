import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import ResultDialog from './ui/ResultDialog'
import InspirationRerollButton from './InspirationRerollButton'
import { api, ApiError, type DiceResultRequestBody } from '@/api/client'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useToast } from '@/hooks/useToast'
import type { RollGroup } from '@/dice/useRollAndPersist'
import { haptic } from '@/auth/telegram'

const MAX_INLINE_ROLLS = 8

function formatRollList(rolls: number[]): string {
  if (rolls.length <= MAX_INLINE_ROLLS) {
    return `[${rolls.join('+')}]`
  }
  const visible = rolls.slice(0, MAX_INLINE_ROLLS).join('+')
  const remaining = rolls.length - MAX_INLINE_ROLLS
  const min = Math.min(...rolls)
  const max = Math.max(...rolls)
  return `[${visible}+… (+${remaining}, min ${min} · max ${max})]`
}

type Props = {
  charId: number
  initialResults: RollGroup[]
  inspirationAvailable: boolean
  onClose: () => void
}

function isPureD20Pool(results: RollGroup[]): boolean {
  return (
    results.length === 1 &&
    results[0].kind === 'd20' &&
    results[0].rolls.length === 1
  )
}

export default function DicePoolResultModal({
  charId,
  initialResults,
  inspirationAvailable,
  onClose,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const toast = useToast()

  const [results, setResults] = useState<RollGroup[]>(initialResults)
  const [wasRerolled, setWasRerolled] = useState(false)

  const rerollMutation = useMutation({
    mutationFn: async () => {
      const useAnimation = animate3d && !reducedMotion
      let dieValue: number
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        dieValue = detected[0]?.value ?? 1
      } else {
        dieValue = Math.floor(Math.random() * 20) + 1
      }
      const body: DiceResultRequestBody = {
        rolls: [{ kind: 'd20', value: dieValue }],
        notation: '1d20',
        with_inspiration: true,
      }
      await api.dice.result(charId, body)
      return { kind: 'd20' as const, notation: '1d20', rolls: [dieValue], total: dieValue }
    },
    onSuccess: (group) => {
      setResults([group])
      setWasRerolled(true)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      qc.invalidateQueries({ queryKey: ['history', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  const total = results.reduce((s, g) => s + g.total, 0)
  const showInspirationButton =
    inspirationAvailable && !wasRerolled && isPureD20Pool(results)

  const handleReroll = useCallback(() => {
    rerollMutation.mutate()
  }, [rerollMutation])

  return (
    <ResultDialog
      open
      onClose={onClose}
      accent="default"
      size="md"
      title={t('character.dice_overlay.result_title')}
      subtitle={wasRerolled ? t('character.inspiration.reroll_badge') : undefined}
      extraActions={
        showInspirationButton ? (
          <InspirationRerollButton
            available
            pending={rerollMutation.isPending}
            onClick={handleReroll}
          />
        ) : undefined
      }
    >
      <div className="space-y-2 max-h-[40vh] overflow-y-auto text-left">
        {results.map((g, i) => (
          <div
            key={i}
            className="flex items-baseline justify-between gap-2 font-mono text-sm"
          >
            <span className="text-dnd-gold-dim min-w-0 flex-1">
              <span className="font-semibold">{g.notation}</span>
              {g.rolls.length > 1 && (
                <span className="text-dnd-text-faint text-[11px] ml-1.5 break-words">
                  {formatRollList(g.rolls)}
                </span>
              )}
            </span>
            <span className="font-display font-black text-dnd-gold-bright text-lg shrink-0">
              {g.total}
            </span>
          </div>
        ))}
      </div>

      {results.length > 1 && (
        <p className="text-dnd-text-muted text-xs font-body">
          {t('common.total')}:{' '}
          <span className="font-display font-black text-dnd-gold-bright text-base">
            {total}
          </span>
        </p>
      )}
    </ResultDialog>
  )
}
