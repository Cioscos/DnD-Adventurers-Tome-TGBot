import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Swords, Send, Minus, Plus, Trash2 } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import DiceIcon from '@/components/ui/DiceIcon'
import { DiceRunicWatermark } from '@/components/ui/Ornament'
import ScrollArea from '@/components/ScrollArea'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import type { DiceRollResult } from '@/types'

const DICE = [4, 6, 8, 10, 12, 20, 100] as const
type DieSide = typeof DICE[number]

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
  const [tumbling, setTumbling] = useState<DieSide | null>(null)

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
      haptic.medium()
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
      haptic.medium()
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

  const handleRoll = (die: DieSide) => {
    setTumbling(die)
    setTimeout(() => setTumbling(null), 400)
    rollMutation.mutate({ die: `d${die}` })
  }

  const dexMod = char?.ability_scores.find((s) => s.name === 'dexterity')?.modifier ?? 0
  const modLabel = dexMod >= 0 ? `+${dexMod}` : String(dexMod)

  return (
    <Layout title={t('character.dice.title')} backTo={`/char/${charId}`} group="tools" page="dice">
      {/* Initiative button */}
      <Button
        variant="arcane"
        size="lg"
        fullWidth
        onClick={() => initiativeMutation.mutate()}
        disabled={initiativeMutation.isPending || rollMutation.isPending}
        loading={initiativeMutation.isPending}
        icon={<Swords size={18} />}
        haptic="medium"
      >
        {t('character.dice.initiative')} (d20 {modLabel})
      </Button>

      {/* Dice count stepper */}
      <Surface variant="elevated">
        <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-2">
          {t('character.dice.count')}
        </p>
        <div className="flex items-center justify-between gap-3">
          <m.button
            onClick={() => setCount((c) => Math.max(1, c - 1))}
            disabled={count <= 1}
            className="w-12 h-12 rounded-2xl bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold disabled:opacity-30"
            whileTap={{ scale: 0.9 }}
          >
            <Minus size={18} />
          </m.button>
          <m.span
            key={count}
            className="text-4xl font-display font-black text-dnd-gold-bright min-w-[3rem] text-center"
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={spring.snappy}
          >
            {count}
          </m.span>
          <m.button
            onClick={() => setCount((c) => Math.min(10, c + 1))}
            disabled={count >= 10}
            className="w-12 h-12 rounded-2xl bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold disabled:opacity-30"
            whileTap={{ scale: 0.9 }}
          >
            <Plus size={18} />
          </m.button>
        </div>
      </Surface>

      {/* Dice tray */}
      <Surface variant="tome" className="relative !p-4">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <DiceRunicWatermark size={200} />
        </div>
        <div className="relative grid grid-cols-4 gap-2">
          {DICE.slice(0, 6).map((die) => (
            <m.button
              key={die}
              onClick={() => handleRoll(die)}
              disabled={rollMutation.isPending || initiativeMutation.isPending}
              className="aspect-square rounded-2xl bg-dnd-surface-raised border border-dnd-border hover:border-dnd-gold/60 hover:shadow-halo-gold transition-[box-shadow,border-color] duration-200 flex items-center justify-center disabled:opacity-40 text-dnd-gold-bright"
              whileTap={{ scale: 0.92 }}
              animate={tumbling === die ? { rotate: [0, 90, 180, 270, 360] } : {}}
              transition={{ duration: 0.4 }}
            >
              <DiceIcon sides={die} size={42} />
            </m.button>
          ))}
          <m.button
            onClick={() => handleRoll(100)}
            disabled={rollMutation.isPending || initiativeMutation.isPending}
            className="col-span-2 rounded-2xl bg-dnd-surface-raised border border-dnd-border hover:border-dnd-gold/60 hover:shadow-halo-gold transition-[box-shadow,border-color] duration-200 flex items-center justify-center gap-2 py-3 disabled:opacity-40 text-dnd-gold-bright"
            whileTap={{ scale: 0.95 }}
            animate={tumbling === 100 ? { rotate: [0, 360] } : {}}
            transition={{ duration: 0.4 }}
          >
            <DiceIcon sides={100} size={34} />
            <span className="font-cinzel font-bold">d100</span>
          </m.button>
        </div>
      </Surface>

      {/* Initiative result */}
      <AnimatePresence>
        {initiativeResult && (
          <m.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10 }}
            transition={spring.elastic}
          >
            <Surface variant="arcane" ornamented className="text-center">
              <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright mb-1 flex items-center justify-center gap-1.5">
                <Swords size={12} /> {t('character.dice.initiative')}
              </p>
              <m.p
                className="text-6xl font-display font-black text-dnd-gold-bright"
                initial={{ scale: 0.5, rotate: -10 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ ...spring.elastic, delay: 0.1 }}
              >
                {initiativeResult.total}
              </m.p>
              <p className="text-xs text-dnd-text-muted font-mono mt-1">
                d20 ({initiativeResult.roll}) {initiativeResult.dexMod >= 0 ? '+' : ''}{initiativeResult.dexMod}
              </p>
            </Surface>
          </m.div>
        )}
      </AnimatePresence>

      {/* Last result */}
      <AnimatePresence>
        {lastResult && (
          <m.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10 }}
            transition={spring.elastic}
          >
            <Surface variant="elevated" ornamented className="text-center">
              <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
                {count > 1 ? `${count}${lastResult.notation}` : lastResult.notation}
              </p>
              <m.p
                className="text-6xl font-display font-black text-dnd-gold-bright"
                initial={{ scale: 0.5 }}
                animate={{ scale: 1 }}
                transition={{ ...spring.elastic, delay: 0.1 }}
              >
                {lastResult.total}
              </m.p>
              {lastResult.rolls.length > 1 && (
                <p className="text-xs text-dnd-text-muted font-mono mt-1">
                  [{lastResult.rolls.join(' + ')}]
                </p>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  haptic.light()
                  api.dice.postToChat(charId, lastResult).catch(() => {})
                }}
                icon={<Send size={14} />}
                className="mt-3"
              >
                {t('character.dice.send_to_chat')}
              </Button>
            </Surface>
          </m.div>
        )}
      </AnimatePresence>

      {/* History */}
      {history.length > 0 && (
        <div>
          <div className="flex justify-between items-center mb-2 px-1">
            <h3 className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">
              {t('character.dice.history')}
            </h3>
            <m.button
              onClick={() => setShowClearConfirm(true)}
              className="text-[10px] text-[var(--dnd-crimson-bright)] flex items-center gap-1 font-cinzel uppercase tracking-wider"
              whileTap={{ scale: 0.95 }}
            >
              <Trash2 size={11} />
              {t('character.dice.clear')}
            </m.button>
          </div>
          <ScrollArea>
            <div className="space-y-1">
              {history.slice(0, 10).map((entry, i) => (
                <m.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="flex justify-between items-center gap-2 px-3 py-2 rounded-xl bg-dnd-surface border border-dnd-border"
                >
                  <div className="flex items-baseline gap-1.5 min-w-0">
                    <span className="text-xs text-dnd-gold-dim font-mono shrink-0">{entry.notation}</span>
                    {entry.rolls.length > 1 && (
                      <span className="text-[10px] text-dnd-text-faint font-mono truncate">
                        [{entry.rolls.join('+')}]
                      </span>
                    )}
                  </div>
                  <span className="font-display font-black text-dnd-gold-bright text-lg shrink-0">{entry.total}</span>
                </m.div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Clear confirmation */}
      <Sheet
        open={showClearConfirm}
        onClose={() => setShowClearConfirm(false)}
        centered
        title={t('character.dice.clear')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {t('character.dice.clear_confirm')}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => clearHistoryMutation.mutate()}
              loading={clearHistoryMutation.isPending}
              haptic="error"
            >
              {t('common.confirm')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setShowClearConfirm(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}
