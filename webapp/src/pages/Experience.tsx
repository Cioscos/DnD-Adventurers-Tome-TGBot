import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, ChevronsUp } from 'lucide-react'
import { GiPolarStar as Star } from 'react-icons/gi'
import { toast } from 'sonner'
import { fireLevelUpConfetti } from '@/lib/celebrate'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import StatPill from '@/components/ui/StatPill'
import AnimatedNumber from '@/components/ui/AnimatedNumber'
import { CornerFlourish } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { spring, ease } from '@/styles/motion'
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'
import { diffResourceMaxes } from '@/lib/resourceDiff'
import { formatInt, localeTag } from '@/lib/format'
import ProgressionPreview from '@/components/character/ProgressionPreview'
import ClassTabs from '@/components/character/ClassTabs'
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import ExperienceSkeleton from '@/components/skeletons/ExperienceSkeleton'
import type { CharacterFull } from '@/types'

function pickDefaultClass(char: CharacterFull): string {
  const classes = char.classes ?? []
  if (classes.length === 0) return ''
  if (classes.length === 1) return classes[0].class_name
  // Multi-class fallback: alphabetic. (No reliable history field on CharacterFull.)
  return [...classes].sort((a, b) => a.class_name.localeCompare(b.class_name))[0].class_name
}

export default function Experience() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [addValue, setAddValue] = useState('')
  const [setMode, setSetMode] = useState(false)
  const [showLevelUpModal, setShowLevelUpModal] = useState(false)
  const [levelUpBurstKey, setLevelUpBurstKey] = useState(0)
  const [selectedClassOverride, setSelectedClassOverride] = useState<string | null>(null)
  const reducedMotion = useReducedMotion()
  // Synchronous guard against double-fire of handleApply (Input.onCommit on blur +
  // button.onClick both fire when the user taps Applica — `mutation.isPending` isn't
  // yet true at the second call). Mirrors AbilityScores.tsx / HP.tsx (finding #2).
  const savingRef = useRef(false)

  useEffect(() => {
    if (!levelUpBurstKey) return
    const t = setTimeout(() => setLevelUpBurstKey(0), 2400)
    return () => clearTimeout(t)
  }, [levelUpBurstKey])

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
        if (!reducedMotion) {
          fireLevelUpConfetti()
          setLevelUpBurstKey((k) => k + 1)
        }
      }
      if (updated.hp_gained && updated.hp_gained > 0) {
        toast.success(t('character.xp.hp_gained_toast', { hp: updated.hp_gained }), {
          duration: 2000,
          icon: '❤',
        })
      }
      // Resource pools that auto-scaled with the class level-up.
      if (char) {
        const diffs = diffResourceMaxes(char.abilities ?? [], updated.abilities ?? [])
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
      savingRef.current = false
    },
    onError: () => {
      haptic.error()
      savingRef.current = false
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.xp.title')} backTo={`/char/${charId}`} group="character" page="xp">
        <ExperienceSkeleton />
      </Layout>
    )
  }

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

  // Derived (never '' when char exists): use the user's tab override when it still
  // points at a current class, otherwise fall back to the default. Auto-recovers when
  // the selected class is removed (multiclass edit) without needing an effect.
  const selectedClass =
    selectedClassOverride && char.classes?.some((c) => c.class_name === selectedClassOverride)
      ? selectedClassOverride
      : pickDefaultClass(char)
  const currentClassEntry = char.classes?.find((c) => c.class_name === selectedClass)
  const currentClassLevel = currentClassEntry?.level ?? 1

  const handleApply = () => {
    if (savingRef.current || mutation.isPending) return
    const n = parseInt(addValue, 10)
    if (isNaN(n)) return
    savingRef.current = true
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
      <Surface
        variant="tome"
        ornamented
        className={`text-center relative overflow-hidden ${levelUpBurstKey ? 'animate-pulse-gold' : ''}`}
      >
        {levelUpBurstKey > 0 && !reducedMotion && (
          <div className="absolute inset-0 pointer-events-none z-[2] text-dnd-gold-bright">
            {[
              { pos: 'top-1 left-1', rot: 0 as const },
              { pos: 'top-1 right-1', rot: 90 as const },
              { pos: 'bottom-1 right-1', rot: 180 as const },
              { pos: 'bottom-1 left-1', rot: 270 as const },
            ].map((corner, i) => (
              <m.div
                key={`${levelUpBurstKey}-${i}`}
                className={`absolute ${corner.pos}`}
                initial={{ scale: 0, opacity: 0, rotate: -10 }}
                animate={{ scale: [0, 1.4, 1], opacity: [0, 1, 0.85], rotate: 0 }}
                transition={{
                  duration: 0.62,
                  delay: i * 0.07,
                  ease: ease.inkSpread,
                }}
              >
                <CornerFlourish rotation={corner.rot} size={18} />
              </m.div>
            ))}
          </div>
        )}
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
          <Star size={14} className="text-dnd-amber" />
          <AnimatedNumber
            value={xp}
            locale={localeTag(i18n.language)}
            className="text-2xl font-display font-bold text-dnd-text"
            stiffness={120}
            damping={26}
          />
          <span className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.xp.label')}</span>
        </div>

        {isMaxLevel && (
          <p className="mt-3 text-sm font-display font-bold text-dnd-gold-bright">
            ★ {t('character.xp.legend')} ★
          </p>
        )}

        {nextThreshold && (
          <div className="mt-4">
            <div className="flex items-center justify-end mb-1.5">
              <StatPill tone="default" size="sm" value={`${formatInt(xpToNext, i18n.language)} ${t('character.xp.label')} → ${level + 1}`} />
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
              <Pressable
                key={m}
                onClick={() => setSetMode(m === 'set')}
                className={`min-h-[44px] rounded-lg font-cinzel text-xs uppercase tracking-widest transition-colors
                  ${isActive
                    ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                    : 'bg-transparent text-dnd-text-muted'}`}
              >
                {m === 'add' ? `+ ${t('character.xp.add')}` : `= ${t('character.currency.mode_set')}`}
              </Pressable>
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
            placeholder={t('character.xp.label')}
            inputMode="numeric"
            onCommit={handleApply}
            className="flex-1"
          />
          <Button
            variant={levelUpAvailable ? 'secondary' : 'primary'}
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
      )}

      {/* Class progression table */}
      {char.classes && char.classes.length > 0 && (
        <div>
          <ClassTabs classes={char.classes} selected={selectedClass} onSelect={setSelectedClassOverride} />
          <ProgressionPreview className={selectedClass} currentLevel={currentClassLevel} isMulticlass={isMulticlass} />
        </div>
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
