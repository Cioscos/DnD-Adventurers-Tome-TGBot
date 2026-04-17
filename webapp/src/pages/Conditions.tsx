import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import {
  EyeOff, Heart, VolumeX, Ghost, Link2, Cloud, Eye, Zap, Mountain,
  FlaskConical, ArrowDown, Lock, Sparkle, Moon, Flame,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'

const CONDITIONS: { key: string; icon: LucideIcon }[] = [
  { key: 'blinded',       icon: EyeOff },
  { key: 'charmed',       icon: Heart },
  { key: 'deafened',      icon: VolumeX },
  { key: 'frightened',    icon: Ghost },
  { key: 'grappled',      icon: Link2 },
  { key: 'incapacitated', icon: Cloud },
  { key: 'invisible',     icon: Eye },
  { key: 'paralyzed',     icon: Zap },
  { key: 'petrified',     icon: Mountain },
  { key: 'poisoned',      icon: FlaskConical },
  { key: 'prone',         icon: ArrowDown },
  { key: 'restrained',    icon: Lock },
  { key: 'stunned',       icon: Sparkle },
  { key: 'unconscious',   icon: Moon },
]

export default function Conditions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [exhaustionLevel, setExhaustionLevel] = useState<number | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  useEffect(() => {
    if (char && exhaustionLevel === null) {
      const conds = (char.conditions as Record<string, unknown>) ?? {}
      if (typeof conds['exhaustion'] === 'number') {
        setExhaustionLevel(conds['exhaustion'] as number)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [char])

  const mutation = useMutation({
    mutationFn: (conditions: Record<string, unknown>) =>
      api.characters.updateConditions(charId, conditions),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const conditions: Record<string, unknown> = (char.conditions as Record<string, unknown>) ?? {}
  const currentExhaustion = typeof conditions['exhaustion'] === 'number'
    ? (conditions['exhaustion'] as number)
    : 0

  const toggle = (key: string) => {
    const current = conditions[key] ?? false
    mutation.mutate({ ...conditions, [key]: !current })
  }

  const setExhaustion = (level: number) => {
    setExhaustionLevel(level)
    mutation.mutate({ ...conditions, exhaustion: level })
  }

  const activeCount = CONDITIONS.filter((c) => conditions[c.key]).length + (currentExhaustion > 0 ? 1 : 0)

  return (
    <Layout title={t('character.conditions.title')} backTo={`/char/${charId}`} group="character" page="conditions">
      {activeCount === 0 && (
        <Surface variant="flat" className="text-center py-5">
          <p className="text-dnd-text-muted font-body italic">
            {t('character.conditions.none_active')}
          </p>
        </Surface>
      )}

      {/* Exhaustion tracker */}
      <Surface variant="elevated" ornamented>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Flame size={16} className="text-[var(--dnd-amber)]" />
            <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-dim">
              {t('character.conditions.exhaustion_condition')}
            </span>
          </div>
          <span className={`text-lg font-display font-black
            ${currentExhaustion > 0 ? 'text-[var(--dnd-amber)]' : 'text-dnd-text-faint'}`}>
            {currentExhaustion}<span className="text-sm text-dnd-text-muted">/6</span>
          </span>
        </div>
        <div className="flex gap-1.5">
          {[0, 1, 2, 3, 4, 5, 6].map((level) => {
            const isActive = (exhaustionLevel ?? currentExhaustion) === level
            const isFilled = level <= (exhaustionLevel ?? currentExhaustion)
            return (
              <m.button
                key={level}
                onClick={() => setExhaustion(level)}
                className={`flex-1 min-h-[40px] rounded-lg font-cinzel font-black text-sm
                  ${isActive
                    ? 'bg-gradient-ember text-white shadow-parchment-md'
                    : isFilled
                      ? 'bg-[var(--dnd-amber)]/40 text-[var(--dnd-amber)]'
                      : 'bg-dnd-surface border border-dnd-border text-dnd-text-faint'}`}
                whileTap={{ scale: 0.92 }}
                transition={spring.press}
              >
                {level}
              </m.button>
            )
          })}
        </div>
      </Surface>

      {/* Condition grid */}
      <m.div
        className="grid grid-cols-2 gap-2"
        initial="initial"
        animate="animate"
        variants={{
          initial: {},
          animate: { transition: { staggerChildren: stagger.listTight } },
        }}
      >
        {CONDITIONS.map((cond) => {
          const Icon = cond.icon
          const active = !!conditions[cond.key]
          return (
            <m.button
              key={cond.key}
              onClick={() => toggle(cond.key)}
              variants={{
                initial: { opacity: 0, y: 8 },
                animate: { opacity: 1, y: 0 },
              }}
              className={`flex items-center gap-2 px-3 py-3 rounded-xl border text-left transition-colors
                ${active
                  ? 'bg-gradient-to-br from-[var(--dnd-crimson-deep)]/40 to-[var(--dnd-crimson)]/20 border-dnd-crimson/60 shadow-halo-danger text-dnd-text'
                  : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}`}
              whileTap={{ scale: 0.95 }}
              animate={active ? { x: [-2, 2, -1, 1, 0] } : {}}
              transition={{ duration: 0.25 }}
            >
              <Icon size={18} className={active ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text-faint'} />
              <span className="text-sm font-body leading-tight">
                {t(`character.conditions.${cond.key}`)}
              </span>
            </m.button>
          )
        })}
      </m.div>
    </Layout>
  )
}
