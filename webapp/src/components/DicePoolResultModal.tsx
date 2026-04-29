import { useCallback, useState } from 'react'
import { m, AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './ui/Ornament'
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
        label: 'Reroll ispirazione',
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
    <AnimatePresence>
      <m.div
        className="fixed inset-0 flex items-center justify-center z-50 p-4"
        style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <m.div
          className="relative rounded-3xl p-6 pt-8 w-full max-w-sm space-y-4
                     bg-gradient-parchment surface-parchment border-2 border-dnd-gold-dim
                     shadow-parchment-2xl"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.85, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={spring.elastic}
        >
          <div className="text-dnd-gold-dim">
            <CornerFlourishes />
          </div>

          <div className="text-center">
            <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
              {t('character.dice_overlay.result_title')}
            </p>
            {wasRerolled && (
              <p className="text-[11px] text-dnd-arcane-bright font-cinzel uppercase tracking-wider mt-1">
                {t('character.inspiration.reroll_badge')}
              </p>
            )}
          </div>

          <div className="space-y-2 max-h-[40vh] overflow-y-auto">
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
            <p className="text-center text-dnd-text-muted text-xs font-body">
              Totale:{' '}
              <span className="font-display font-black text-dnd-gold-bright text-base">
                {total}
              </span>
            </p>
          )}

          {showInspirationButton && (
            <InspirationRerollButton
              available
              pending={rerollMutation.isPending}
              onClick={handleReroll}
            />
          )}

          <m.button
            type="button"
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold
                       min-h-[48px] shadow-engrave font-cinzel uppercase tracking-wider"
            whileTap={{ scale: 0.97 }}
          >
            OK
          </m.button>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
