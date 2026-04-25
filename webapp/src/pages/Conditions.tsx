import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Info } from 'lucide-react'
import { GiFlame as Flame } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import { CONDITION_ICONS } from '@/lib/conditions'

const CONDITION_KEYS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'prone', 'restrained', 'stunned', 'unconscious',
] as const

export default function Conditions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [exhaustionLevel, setExhaustionLevel] = useState<number | null>(null)
  const [detailKey, setDetailKey] = useState<string | null>(null)
  const [showExhaustionDetails, setShowExhaustionDetails] = useState(false)

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

  const activeCount = CONDITION_KEYS.filter((k) => conditions[k]).length + (currentExhaustion > 0 ? 1 : 0)

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
            <button
              type="button"
              aria-label={t('character.conditions.detail_aria')}
              aria-expanded={showExhaustionDetails}
              onClick={() => setShowExhaustionDetails((v) => !v)}
              className={`transition-colors ${
                showExhaustionDetails
                  ? 'text-dnd-gold-bright'
                  : 'text-dnd-text-muted hover:text-dnd-gold-bright'
              }`}
            >
              <Info size={14} />
            </button>
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
        {/* Exhaustion details — intro + 6 level descriptions, toggled by Info button */}
        {showExhaustionDetails && (() => {
          const intro = t('character.conditions.desc.exhaustion') as string
          const levels = t('character.conditions.desc.exhaustion_levels', {
            returnObjects: true,
          }) as string[]
          return (
            <div className="mt-4 space-y-2">
              <p className="text-sm text-dnd-text font-body leading-relaxed">
                {intro}
              </p>
              <div className="space-y-1 text-sm">
                {levels.map((desc, idx) => {
                  const lvl = idx + 1
                  const isCurrent = lvl === currentExhaustion
                  return (
                    <div
                      key={lvl}
                      className={
                        isCurrent
                          ? 'px-3 py-2 rounded-md border-l-2 border-dnd-gold bg-dnd-gold/10 text-dnd-gold-bright'
                          : 'px-3 py-1.5 text-dnd-text-faint opacity-60'
                      }
                    >
                      {desc}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })()}
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
        {CONDITION_KEYS.map((key) => {
          const Icon = CONDITION_ICONS[key]
          const active = !!conditions[key]
          return (
            <m.div
              key={key}
              variants={{
                initial: { opacity: 0, y: 8 },
                animate: { opacity: 1, y: 0 },
              }}
              className={`flex items-center rounded-xl border transition-colors
                ${active
                  ? 'bg-gradient-to-br from-[var(--dnd-crimson-deep)]/40 to-[var(--dnd-crimson)]/20 border-dnd-crimson/60 shadow-halo-danger text-dnd-text'
                  : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}`}
              animate={active ? { x: [-2, 2, -1, 1, 0] } : {}}
              transition={{ duration: 0.25 }}
            >
              <m.button
                type="button"
                onClick={() => toggle(key)}
                whileTap={{ scale: 0.95 }}
                className="flex-1 flex items-center gap-2 px-3 py-3 text-left"
              >
                <Icon size={18} className={active ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text-faint'} />
                <span className="text-sm font-body leading-tight">
                  {t(`character.conditions.${key}`)}
                </span>
              </m.button>
              <button
                type="button"
                aria-label={t('character.conditions.detail_aria')}
                onClick={() => setDetailKey(key)}
                className="shrink-0 p-3 text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
              >
                <Info size={16} />
              </button>
            </m.div>
          )
        })}
      </m.div>
      {detailKey !== null && (
        <ConditionDetailModal
          condKey={detailKey}
          exhaustionLevel={currentExhaustion}
          onClose={() => setDetailKey(null)}
        />
      )}
    </Layout>
  )
}
