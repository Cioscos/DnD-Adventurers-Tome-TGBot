import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, X } from 'lucide-react'
import {
  GiDiceSixFacesOne as Dice1, GiHeartPlus as Heart,
  GiSkullCrossedBones as Skull,
} from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import { spring } from '@/styles/motion'

interface DeathSavesProps {
  deathSaves: { successes: number; failures: number; stable: boolean }
  onRoll: () => void
  onAction: (action: string) => void
  isRolling: boolean
  /** action string currently in flight on the shared deathMutation (P4 scoping), undefined when none. */
  pendingAction?: string
}

type PipTone = 'emerald' | 'crimson'

interface PipGroupProps {
  label: string
  count: number
  tone: PipTone
  icon: React.ReactNode
  urgent?: boolean
}

function PipGroup({ label, count, tone, icon, urgent = false }: PipGroupProps) {
  const fillBg = tone === 'emerald' ? 'bg-dnd-emerald' : 'bg-dnd-crimson'
  const fillBorder = tone === 'emerald'
    ? 'border-dnd-emerald-bright'
    : 'border-dnd-crimson-bright'
  const emptyBorder = tone === 'emerald'
    ? 'border-dnd-emerald/35'
    : 'border-dnd-crimson/35'
  const labelColor = tone === 'emerald'
    ? 'text-dnd-emerald/85'
    : 'text-dnd-crimson/85'
  const glow = tone === 'emerald'
    ? 'shadow-[0_0_8px_rgba(63,166,106,0.5)]'
    : 'shadow-[0_0_8px_rgba(179,58,58,0.5)]'
  const urgentGlow = urgent
    ? 'shadow-[0_0_18px_rgba(179,58,58,0.85)]'
    : ''
  const iconColor = tone === 'emerald' ? 'text-dnd-ink' : 'text-dnd-parchment'

  return (
    <div className="flex flex-col items-center gap-2">
      <p className={`text-[10px] font-cinzel uppercase tracking-widest ${labelColor}`}>
        {label}
      </p>
      <div className={`flex gap-2 ${urgent ? 'animate-pulse' : ''}`}>
        {[0, 1, 2].map((i) => {
          const filled = i < count
          return (
            <m.div
              key={i}
              className={`w-9 h-9 rounded-full border-2 flex items-center justify-center
                ${filled
                  ? `${fillBg} ${fillBorder} ${urgent ? urgentGlow : glow}`
                  : emptyBorder}`}
              animate={filled ? { scale: [0.7, 1.15, 1] } : { scale: 1 }}
              transition={spring.elastic}
            >
              {filled && <span className={iconColor}>{icon}</span>}
            </m.div>
          )
        })}
      </div>
    </div>
  )
}

export default function DeathSaves({ deathSaves, onRoll, onAction, isRolling, pendingAction }: DeathSavesProps) {
  const { t } = useTranslation()
  const successes = deathSaves.successes ?? 0
  const failures = deathSaves.failures ?? 0

  return (
    <Surface variant="ember" ornamented className="flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <Skull size={18} className="text-dnd-crimson-bright" />
        <h3 className="font-display font-bold text-dnd-crimson-bright text-base tracking-wide">
          {t('character.death_saves.title')}
        </h3>
      </div>

      <div className="flex items-center justify-center gap-7">
        <PipGroup
          label={t('character.death_saves.successes')}
          count={successes}
          tone="emerald"
          icon={<Check size={16} strokeWidth={3} />}
        />
        <div className="h-14 w-px bg-dnd-border" aria-hidden />
        <PipGroup
          label={t('character.death_saves.failures')}
          count={failures}
          tone="crimson"
          icon={<X size={16} strokeWidth={3} />}
          urgent={failures >= 2}
        />
      </div>

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={onRoll}
        disabled={isRolling}
        loading={isRolling}
        icon={<Dice1 size={18} />}
        haptic="medium"
        className="mt-5"
      >
        {t('character.death_saves.roll')}
      </Button>

      <div className="flex flex-col gap-3 pt-4 border-t border-dnd-border/40">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-text-muted">
            {t('character.death_saves.manual_override')}
          </p>
          <Pressable
            onClick={() => onAction('reset')}
            pending={pendingAction === 'reset'}
            spinnerSize={12}
            className="inline-flex items-center justify-center
                       min-h-[32px] px-2 rounded
                       text-[10px] font-cinzel uppercase tracking-widest
                       text-dnd-text-muted hover:text-dnd-gold-bright
                       transition-colors"
          >
            {t('character.death_saves.reset')}
          </Pressable>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onAction('success')}
            loading={pendingAction === 'success'}
            icon={<Check size={14} />}
            className="!bg-dnd-emerald/15 !border-dnd-emerald/40 !text-dnd-emerald-bright"
          >
            {t('character.death_saves.success')}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onAction('failure')}
            loading={pendingAction === 'failure'}
            icon={<X size={14} />}
            className="!bg-dnd-crimson/15 !border-dnd-crimson/40 !text-dnd-crimson-bright"
          >
            {t('character.death_saves.failure')}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onAction('stabilize')}
            loading={pendingAction === 'stabilize'}
            icon={<Heart size={14} />}
            className="!bg-dnd-cobalt/15 !border-dnd-cobalt/40 !text-dnd-cobalt-bright"
          >
            {t('character.death_saves.stabilize')}
          </Button>
        </div>
      </div>
    </Surface>
  )
}
