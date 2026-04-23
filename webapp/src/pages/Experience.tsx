import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Sparkles, Star, Check, ChevronsUp } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { XP_THRESHOLDS, levelFromXp, quickXpAmounts } from '@/lib/xpThresholds'

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
      if (updated.hp_gained && updated.hp_gained > 0) {
        toast.success(t('character.xp.hp_gained_toast', { hp: updated.hp_gained }), {
          duration: 2000,
          icon: '❤',
        })
      }
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
  const isMaxLevel = level >= 20
  const quickAmounts = quickXpAmounts(xpToNext)

  const handleApply = () => {
    const n = parseInt(addValue, 10)
    if (isNaN(n)) return
    mutation.mutate(setMode ? { set: n } : { add: n })
  }

  const handleLevelUp = () => {
    if (nextThreshold === null) return
    mutation.mutate({ set: nextThreshold })
  }

  return (
    <Layout title={t('character.xp.title')} backTo={`/char/${charId}`} group="character" page="xp">
      {/* Level-up notification */}
      {levelUpAvailable && (
        <m.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={spring.elastic}
          className="rounded-2xl bg-gradient-gold border border-dnd-gold text-dnd-ink px-4 py-3 text-sm font-cinzel uppercase tracking-wider flex items-center gap-2 shadow-parchment-lg"
        >
          <Sparkles size={16} className="animate-shimmer" />
          {t('character.xp.level_up_available')}
        </m.div>
      )}

      {isSingleClass && (
        <p className="text-xs text-dnd-text-muted text-center italic font-body">
          {t('character.xp.single_class_synced')}
        </p>
      )}

      {/* Hero level + XP */}
      <Surface variant="tome" ornamented className="text-center relative overflow-hidden">
        <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim mb-1">
          {t('character.xp.level_abbr')}
        </p>
        <m.p
          key={level}
          className="text-7xl font-display font-black text-dnd-gold-bright leading-none"
          style={{ textShadow: '0 3px 12px var(--dnd-gold-glow)' }}
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: [0.6, 1.1, 1], opacity: 1 }}
          transition={spring.elastic}
        >
          {level}
        </m.p>

        <div className="flex items-center justify-center gap-2 mt-3">
          <Star size={14} className="text-[var(--dnd-amber)]" />
          <p className="text-2xl font-display font-bold text-dnd-text font-mono">{xp.toLocaleString()}</p>
          <span className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">XP</span>
        </div>

        {nextThreshold && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-1.5">
              <StatPill tone="gold" size="sm" value={`${level}`} label="Lv" />
              <StatPill tone="default" size="sm" value={`${xpToNext.toLocaleString()} XP → ${level + 1}`} />
            </div>
            {/* XP progress bar */}
            <div className="h-3 rounded-full bg-dnd-ink/60 overflow-hidden border border-dnd-border relative">
              <m.div
                className="h-full rounded-full bg-gradient-gold shadow-[inset_0_1px_0_rgba(255,220,140,0.3)]"
                initial={false}
                animate={{ width: `${progress}%` }}
                transition={spring.drift}
              />
              {/* Threshold ticks at 25/50/75% */}
              {[25, 50, 75].map((mark) => (
                <div
                  key={mark}
                  className="absolute top-0 bottom-0 w-px bg-dnd-gold-dim/40"
                  style={{ left: `${mark}%` }}
                />
              ))}
            </div>
            <p className="text-[10px] text-dnd-text-faint font-mono mt-1 text-right">{progress}%</p>
          </div>
        )}
      </Surface>

      {/* Mode toggle */}
      <Surface variant="flat" className="!p-1.5">
        <div className="grid grid-cols-2 gap-1">
          {(['add', 'set'] as const).map((m) => {
            const isActive = setMode ? m === 'set' : m === 'add'
            return (
              <button
                key={m}
                onClick={() => setSetMode(m === 'set')}
                className={`min-h-[40px] rounded-lg font-cinzel text-xs uppercase tracking-widest transition-colors
                  ${isActive
                    ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                    : 'bg-transparent text-dnd-text-muted'}`}
              >
                {m === 'add' ? `+ ${t('character.xp.add')}` : `= ${t('character.currency.mode_set')}`}
              </button>
            )
          })}
        </div>
      </Surface>

      <Surface variant="elevated">
        <div className="flex gap-3 items-end">
          <Input
            type="number"
            min={0}
            value={addValue}
            onChange={setAddValue}
            placeholder="XP"
            inputMode="numeric"
            onCommit={handleApply}
            className="flex-1"
          />
          <Button
            variant="primary"
            size="md"
            onClick={handleApply}
            disabled={!addValue}
            loading={mutation.isPending}
            icon={<Check size={16} />}
            haptic="success"
          />
        </div>
      </Surface>

      {!isMaxLevel && (
        <>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onClick={handleLevelUp}
            loading={mutation.isPending}
            icon={<ChevronsUp size={18} />}
            haptic="medium"
            aria-label={t('character.xp.level_up_to', { level: level + 1 })}
          >
            <span className="font-cinzel tracking-widest uppercase">
              {t('character.xp.level_up_cta')}
            </span>
          </Button>

          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: `repeat(${quickAmounts.length}, minmax(0, 1fr))` }}
          >
            {quickAmounts.map((n) => (
              <m.button
                key={n}
                onClick={() => mutation.mutate({ add: n })}
                disabled={mutation.isPending}
                className="min-h-[48px] rounded-xl bg-dnd-surface border border-dnd-border
                           hover:border-dnd-gold/60 transition-colors
                           font-mono font-bold text-dnd-gold-bright
                           disabled:opacity-40 disabled:pointer-events-none"
                whileTap={{ scale: 0.93 }}
              >
                +{n}
              </m.button>
            ))}
          </div>
        </>
      )}
    </Layout>
  )
}
