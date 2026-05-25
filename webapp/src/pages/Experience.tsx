import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, ChevronsUp } from 'lucide-react'
import { GiPolarStar as Star } from 'react-icons/gi'
import { toast } from 'sonner'
import confetti from 'canvas-confetti'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import { haptic } from '@/auth/telegram'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { spring } from '@/styles/motion'
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'
import { diffResourceMaxes } from '@/lib/resourceDiff'

// Two-burst gold/arcane confetti from bottom corners. Respect reduced-motion.
function fireLevelUpConfetti() {
  const palette = ['#f4d06f', '#d4a64a', '#a78bfa', '#fff6c2']
  const base = { spread: 60, startVelocity: 45, ticks: 200, gravity: 0.8, colors: palette, zIndex: 9999 } as const
  confetti({ ...base, particleCount: 70, angle: 60, origin: { x: 0.05, y: 0.9 } })
  confetti({ ...base, particleCount: 70, angle: 120, origin: { x: 0.95, y: 0.9 } })
}

// Fixed quick-add amounts (audit P2: replace dynamic quickXpAmounts with stable values).
const FIXED_QUICK_AMOUNTS = [10, 50, 100, 500] as const

// D&D 5e DMG p.82 — per-character XP threshold by encounter difficulty (level 1-20).
// We award the *Medium* threshold per character on Medium, etc. Players usually log
// the XP for the *party*; this preset is a per-character estimate to make quick-logging
// a typical 4-PC encounter trivial.
const ENCOUNTER_XP: Record<number, { easy: number; medium: number; hard: number; deadly: number }> = {
  1:  { easy: 25,    medium: 50,    hard: 75,    deadly: 100 },
  2:  { easy: 50,    medium: 100,   hard: 150,   deadly: 200 },
  3:  { easy: 75,    medium: 150,   hard: 225,   deadly: 400 },
  4:  { easy: 125,   medium: 250,   hard: 375,   deadly: 500 },
  5:  { easy: 250,   medium: 500,   hard: 750,   deadly: 1100 },
  6:  { easy: 300,   medium: 600,   hard: 900,   deadly: 1400 },
  7:  { easy: 350,   medium: 750,   hard: 1100,  deadly: 1700 },
  8:  { easy: 450,   medium: 900,   hard: 1400,  deadly: 2100 },
  9:  { easy: 550,   medium: 1100,  hard: 1600,  deadly: 2400 },
  10: { easy: 600,   medium: 1200,  hard: 1900,  deadly: 2800 },
  11: { easy: 800,   medium: 1600,  hard: 2400,  deadly: 3600 },
  12: { easy: 1000,  medium: 2000,  hard: 3000,  deadly: 4500 },
  13: { easy: 1100,  medium: 2200,  hard: 3400,  deadly: 5100 },
  14: { easy: 1250,  medium: 2500,  hard: 3800,  deadly: 5700 },
  15: { easy: 1400,  medium: 2800,  hard: 4300,  deadly: 6400 },
  16: { easy: 1600,  medium: 3200,  hard: 4800,  deadly: 7200 },
  17: { easy: 2000,  medium: 3900,  hard: 5900,  deadly: 8800 },
  18: { easy: 2100,  medium: 4200,  hard: 6300,  deadly: 9500 },
  19: { easy: 2400,  medium: 4900,  hard: 7300,  deadly: 10900 },
  20: { easy: 2800,  medium: 5700,  hard: 8500,  deadly: 12700 },
}
const ENCOUNTER_KEYS = ['easy', 'medium', 'hard', 'deadly'] as const
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'

export default function Experience() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [addValue, setAddValue] = useState('')
  const [setMode, setSetMode] = useState(false)
  const [showLevelUpModal, setShowLevelUpModal] = useState(false)
  const reducedMotion = useReducedMotion()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: ({ add, set }: { add?: number; set?: number }) =>
      api.characters.updateXP(charId, { add, set }),
    onSuccess: (updated) => {
      const oldLevel = char ? levelFromXp(char.experience_points) : 0
      const newLevel = levelFromXp(updated.experience_points)
      qc.setQueryData(['character', charId], updated)
      setAddValue('')
      haptic.success()
      if (newLevel > oldLevel) {
        toast.success(t('character.xp.level_up_toast', { level: newLevel }), {
          duration: 3500,
          icon: '✨',
        })
        if (!reducedMotion) fireLevelUpConfetti()
      }
      if (updated.hp_gained && updated.hp_gained > 0) {
        toast.success(t('character.xp.hp_gained_toast', { hp: updated.hp_gained }), {
          duration: 2000,
          icon: '❤',
        })
      }
      // Resource pools that auto-scaled with the class level-up.
      if (char) {
        const diffs = diffResourceMaxes(char.classes ?? [], updated.classes ?? [])
        for (const d of diffs) {
          toast.success(
            t('character.multiclass.resource_max_increased', {
              name: d.name,
              prev: d.prev,
              next: d.next,
              defaultValue: '{{name}}: massimo {{prev}} → {{next}}',
            }),
            { duration: 3500, icon: '⚡' },
          )
        }
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
      {/* Level-up notification — clickable for multiclass */}
      {levelUpAvailable && (
        <LevelUpBanner onOpen={() => setShowLevelUpModal(true)} />
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
          className="text-7xl font-display font-black text-dnd-gold-bright leading-none tabular-nums"
          style={{ textShadow: '0 3px 12px var(--dnd-gold-glow)' }}
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: [0.6, 1.1, 1], opacity: 1 }}
          transition={spring.elastic}
        >
          {level}
        </m.p>

        {levelUpAvailable && (
          <p className="mt-2 text-[10px] font-mono text-dnd-text-muted tabular-nums">
            {t('character.xp.level_distributed_hint', {
              distributed: totalClassLevel,
              pending: level - totalClassLevel,
            })}
          </p>
        )}

        <div className="flex items-center justify-center gap-2 mt-3">
          <Star size={14} className="text-[var(--dnd-amber)]" />
          <p className="text-2xl font-display font-bold text-dnd-text font-mono tabular-nums">{xp.toLocaleString()}</p>
          <span className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">XP</span>
        </div>

        {isMaxLevel && (
          <p className="mt-3 text-sm font-display font-bold text-dnd-gold-bright">
            ★ {t('character.xp.legend')} ★
          </p>
        )}

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
                className={`min-h-[44px] rounded-lg font-cinzel text-xs uppercase tracking-widest transition-colors
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
          >
            {t('common.applica')}
          </Button>
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

          {/* Encounter presets — per-character XP by difficulty (D&D 5e DMG). */}
          <div>
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">
              {t('character.xp.encounter_label', { defaultValue: 'Incontro completato' })}
            </p>
            <div className="grid grid-cols-4 gap-2">
              {ENCOUNTER_KEYS.map((diff) => {
                const lookup = ENCOUNTER_XP[Math.max(1, Math.min(20, level))] ?? ENCOUNTER_XP[20]
                const amount = lookup[diff]
                return (
                  <m.button
                    key={diff}
                    onClick={() => mutation.mutate({ add: amount })}
                    disabled={mutation.isPending}
                    className="min-h-[48px] rounded-xl bg-dnd-surface border border-dnd-border
                               hover:border-dnd-gold/60 transition-colors
                               flex flex-col items-center justify-center gap-0.5
                               disabled:opacity-40 disabled:pointer-events-none"
                    whileTap={{ scale: 0.93 }}
                    aria-label={t(`character.xp.encounter_${diff}`, { defaultValue: diff })}
                  >
                    <span className="text-[10px] font-cinzel uppercase tracking-wider text-dnd-text-muted">
                      {t(`character.xp.encounter_${diff}`, { defaultValue: diff })}
                    </span>
                    <span className="text-[11px] font-mono font-bold text-dnd-gold-bright tabular-nums">
                      +{amount}
                    </span>
                  </m.button>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {FIXED_QUICK_AMOUNTS.map((n) => (
              <m.button
                key={n}
                onClick={() => mutation.mutate({ add: n })}
                disabled={mutation.isPending}
                className="min-h-[48px] rounded-xl bg-dnd-surface border border-dnd-border
                           hover:border-dnd-gold/60 transition-colors
                           font-mono font-bold text-dnd-gold-bright tabular-nums
                           disabled:opacity-40 disabled:pointer-events-none"
                whileTap={{ scale: 0.93 }}
              >
                +{n}
              </m.button>
            ))}
            {xpToNext > 0 && (
              <m.button
                onClick={() => mutation.mutate({ add: Math.max(1, Math.floor(xpToNext / 2)) })}
                disabled={mutation.isPending}
                className="min-h-[48px] rounded-xl bg-dnd-chip-bg border border-dnd-gold/60
                           text-dnd-gold-bright font-cinzel text-[10px] uppercase tracking-widest
                           disabled:opacity-40 disabled:pointer-events-none"
                whileTap={{ scale: 0.93 }}
                aria-label={t('character.xp.quick_half_next', { defaultValue: '+½ livello' })}
                title={`+${Math.max(1, Math.floor(xpToNext / 2))} XP`}
              >
                {t('character.xp.quick_half_next', { defaultValue: '+½ liv' })}
              </m.button>
            )}
          </div>
        </>
      )}
      {showLevelUpModal && (
        <LevelUpModal
          char={char}
          xpLevel={level}
          onClose={() => setShowLevelUpModal(false)}
        />
      )}
    </Layout>
  )
}
