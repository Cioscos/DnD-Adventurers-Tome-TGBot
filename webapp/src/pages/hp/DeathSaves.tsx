import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'

interface DeathSavesProps {
  deathSaves: { successes: number; failures: number; stable: boolean }
  onRoll: () => void
  onAction: (action: string) => void
  isRolling: boolean
}

export default function DeathSaves({ deathSaves, onRoll, onAction, isRolling }: DeathSavesProps) {
  const { t } = useTranslation()

  return (
    <Card variant="elevated">
      <h3 className="font-semibold mb-3">{'\uD83D\uDC80'} {t('character.death_saves.title')}</h3>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="text-center">
          <p className="text-sm text-dnd-text-secondary mb-1">
            {t('character.death_saves.successes')}
          </p>
          <div className="flex justify-center gap-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className={`w-6 h-6 rounded-full border-2 ${
                  i < (deathSaves.successes ?? 0)
                    ? 'bg-dnd-success border-dnd-success'
                    : 'border-white/30'
                }`}
              />
            ))}
          </div>
        </div>
        <div className="text-center">
          <p className="text-sm text-dnd-text-secondary mb-1">
            {t('character.death_saves.failures')}
          </p>
          <div className="flex justify-center gap-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className={`w-6 h-6 rounded-full border-2 ${
                  i < (deathSaves.failures ?? 0)
                    ? 'bg-[var(--dnd-danger)] border-[var(--dnd-danger)]'
                    : 'border-white/30'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
      <button
        onClick={onRoll}
        disabled={isRolling}
        className="w-full py-3 rounded-xl bg-[var(--dnd-gold-glow)] text-dnd-gold font-bold text-base
                   active:opacity-70 disabled:opacity-40 mb-2"
      >
        {'\uD83C\uDFB2'} {t('character.death_saves.roll')}
      </button>
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={() => onAction('success')}
          className="py-2 rounded-xl bg-dnd-success/20 text-[#2ecc71] text-sm font-medium"
        >
          {'\u2713'} {t('character.death_saves.success')}
        </button>
        <button
          onClick={() => onAction('failure')}
          className="py-2 rounded-xl bg-[var(--dnd-danger)]/20 text-[var(--dnd-danger)] text-sm font-medium"
        >
          {'\u2717'} {t('character.death_saves.failure')}
        </button>
        <button
          onClick={() => onAction('stabilize')}
          className="py-2 rounded-xl bg-dnd-info/20 text-[#5dade2] text-sm font-medium"
        >
          {'\uD83D\uDC8A'} {t('character.death_saves.stabilize')}
        </button>
      </div>
      <button
        onClick={() => onAction('reset')}
        className="w-full mt-2 py-2 rounded-xl bg-dnd-surface text-sm"
      >
        {t('character.death_saves.reset')}
      </button>
    </Card>
  )
}
