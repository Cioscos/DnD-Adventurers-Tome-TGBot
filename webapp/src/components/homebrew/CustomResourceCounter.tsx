import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, Minus, RotateCcw } from 'lucide-react'
import { GiCrystalBall } from 'react-icons/gi'
import type { HomebrewResource } from '@/lib/homebrew/types'

interface CustomResourceCounterProps {
  resource: HomebrewResource
  onDecrement: () => void
  onIncrement: () => void
  onRestore: () => void
  isPending?: boolean
}

/**
 * Renders a single homebrew `ResourceDef`-spawned resource (e.g. Luck
 * Points) on the Abilities page. Visually mirrors the class-ability
 * counter band from Abilities.tsx (crimson minus / emerald plus, 44×44
 * touch targets, tabular-nums numerics) so the page reads as one
 * coherent surface — but flags the row as homebrew-sourced via the
 * GiCrystalBall icon + "Regola personalizzata" caption.
 *
 * The "Recupera" chip is a one-tap restore-to-max — only shown when
 * `current < max` to keep the card quiet when nothing's actionable.
 */
export default function CustomResourceCounter({
  resource,
  onDecrement,
  onIncrement,
  onRestore,
  isPending = false,
}: CustomResourceCounterProps) {
  const { t } = useTranslation()

  const atMin = resource.current <= 0
  const atMax = resource.current >= resource.max

  const restorationCaption = t(
    `character.homebrew.resources.restoration_caption_${resource.restoration_type}`,
    { defaultValue: '' },
  )

  return (
    <div
      className="rounded-2xl border border-dnd-gold-dim/30 bg-dnd-surface-raised
                 overflow-hidden shadow-parchment-md"
    >
      <div className="flex items-center gap-2 px-3 py-2.5">
        <span className="shrink-0 inline-flex w-8 h-8 items-center justify-center
                         rounded-lg bg-dnd-gold/10 text-dnd-gold-bright">
          <GiCrystalBall size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display font-bold text-sm text-dnd-gold-bright truncate">
            {resource.name}
          </div>
          <div className="text-[10px] font-cinzel uppercase tracking-[0.18em] text-dnd-text-faint truncate">
            {t('character.homebrew.resources.subtitle')}
          </div>
        </div>
      </div>

      <div className="px-3 pb-3 space-y-2 border-t border-dnd-gold-dim/15">
        {restorationCaption && (
          <div className="flex items-center gap-1.5 pt-2 text-[10px] text-dnd-text-muted font-cinzel uppercase tracking-widest">
            <RotateCcw size={11} />
            <span>{restorationCaption}</span>
          </div>
        )}

        <div className="flex items-center gap-3 rounded-xl bg-dnd-surface border border-dnd-border p-2">
          <m.button
            type="button"
            onClick={onDecrement}
            disabled={atMin || isPending}
            aria-label={t('character.homebrew.resources.aria_decrement', { name: resource.name })}
            className="w-11 h-11 rounded-xl bg-dnd-crimson/15 text-[var(--dnd-crimson-bright)]
                       border border-dnd-crimson/30 flex items-center justify-center
                       disabled:opacity-30"
            whileTap={{ scale: 0.9 }}
          >
            <Minus size={16} />
          </m.button>
          <div className="flex-1 text-center">
            <p className="text-lg font-display font-black text-dnd-gold-bright">
              <span className="font-mono tabular-nums">{resource.current}</span>
              <span className="text-sm text-dnd-text-muted"> / </span>
              <span className="text-sm text-dnd-text-muted font-mono tabular-nums">{resource.max}</span>
            </p>
          </div>
          <m.button
            type="button"
            onClick={onIncrement}
            disabled={atMax || isPending}
            aria-label={t('character.homebrew.resources.aria_increment', { name: resource.name })}
            className="w-11 h-11 rounded-xl bg-dnd-emerald/15 text-[var(--dnd-emerald-bright)]
                       border border-dnd-emerald/30 flex items-center justify-center
                       disabled:opacity-30"
            whileTap={{ scale: 0.9 }}
          >
            <Plus size={16} />
          </m.button>
        </div>

        {!atMax && (
          <div className="flex">
            <m.button
              type="button"
              onClick={onRestore}
              disabled={isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                         bg-dnd-gold/10 border border-dnd-gold-dim/40 text-dnd-gold-bright
                         text-[11px] font-cinzel uppercase tracking-wider
                         disabled:opacity-40"
              whileTap={{ scale: 0.95 }}
            >
              <RotateCcw size={12} />
              {t('character.homebrew.resources.restore')}
            </m.button>
          </div>
        )}
      </div>
    </div>
  )
}
