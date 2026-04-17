import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Dice1, Check, X, Heart, Skull } from 'lucide-react'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { spring } from '@/styles/motion'

interface DeathSavesProps {
  deathSaves: { successes: number; failures: number; stable: boolean }
  onRoll: () => void
  onAction: (action: string) => void
  isRolling: boolean
}

export default function DeathSaves({ deathSaves, onRoll, onAction, isRolling }: DeathSavesProps) {
  const { t } = useTranslation()

  return (
    <Surface variant="ember" ornamented className="space-y-3">
      <div className="flex items-center gap-2">
        <Skull size={18} className="text-[var(--dnd-crimson-bright)]" />
        <h3 className="font-display font-bold text-dnd-gold-bright text-base">
          {t('character.death_saves.title')}
        </h3>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="text-center">
          <p className="text-[10px] text-dnd-text-muted mb-2 font-cinzel uppercase tracking-widest">
            {t('character.death_saves.successes')}
          </p>
          <div className="flex justify-center gap-2">
            {[0, 1, 2].map((i) => {
              const filled = i < (deathSaves.successes ?? 0)
              return (
                <m.div
                  key={i}
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center
                    ${filled
                      ? 'bg-dnd-emerald border-dnd-emerald-bright shadow-[0_0_8px_rgba(63,166,106,0.5)]'
                      : 'border-dnd-border'}`}
                  animate={filled ? { scale: [0.7, 1.15, 1] } : { scale: 1 }}
                  transition={spring.elastic}
                >
                  {filled && <Check size={14} className="text-dnd-ink" strokeWidth={3} />}
                </m.div>
              )
            })}
          </div>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-dnd-text-muted mb-2 font-cinzel uppercase tracking-widest">
            {t('character.death_saves.failures')}
          </p>
          <div className="flex justify-center gap-2">
            {[0, 1, 2].map((i) => {
              const filled = i < (deathSaves.failures ?? 0)
              return (
                <m.div
                  key={i}
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center
                    ${filled
                      ? 'bg-dnd-crimson border-[var(--dnd-crimson-bright)] shadow-[0_0_8px_rgba(179,58,58,0.5)]'
                      : 'border-dnd-border'}`}
                  animate={filled ? { scale: [0.7, 1.15, 1] } : { scale: 1 }}
                  transition={spring.elastic}
                >
                  {filled && <X size={14} className="text-white" strokeWidth={3} />}
                </m.div>
              )
            })}
          </div>
        </div>
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
      >
        {t('character.death_saves.roll')}
      </Button>

      <div className="grid grid-cols-3 gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction('success')}
          icon={<Check size={14} />}
          className="!bg-[var(--dnd-emerald)]/15 !border-dnd-emerald/40 !text-[var(--dnd-emerald-bright)]"
        >
          {t('character.death_saves.success')}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction('failure')}
          icon={<X size={14} />}
          className="!bg-[var(--dnd-crimson)]/15 !border-dnd-crimson/40 !text-[var(--dnd-crimson-bright)]"
        >
          {t('character.death_saves.failure')}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction('stabilize')}
          icon={<Heart size={14} />}
          className="!bg-[var(--dnd-cobalt)]/15 !border-dnd-cobalt/40 !text-[var(--dnd-cobalt-bright)]"
        >
          {t('character.death_saves.stabilize')}
        </Button>
      </div>

      <Button variant="ghost" size="sm" fullWidth onClick={() => onAction('reset')}>
        {t('character.death_saves.reset')}
      </Button>
    </Surface>
  )
}
