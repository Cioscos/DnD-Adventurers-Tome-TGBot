import { useMemo, useState, useCallback } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Dices } from 'lucide-react'
import DiceIcon from '@/components/ui/DiceIcon'
import { useCharacterStore } from '@/store/characterStore'
import { haptic } from '@/auth/telegram'
import type { DiceKind } from '@/dice/types'

const KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const SIDES_FOR = {
  d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 100,
} as const satisfies Record<DiceKind, number>

type DicePool = Partial<Record<DiceKind, number>>

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname
    if (matchPath('/char/:id/dice', path)) return { visible: false, charId: null }

    const charAny = matchPath('/char/:id/*', path) ?? matchPath('/char/:id', path)
    if (charAny) {
      const id = Number(charAny.params.id)
      return { visible: Number.isFinite(id), charId: Number.isFinite(id) ? id : null }
    }

    if (matchPath('/session/:id', path) && activeCharId != null) {
      return { visible: true, charId: activeCharId }
    }

    return { visible: false, charId: null }
  }, [location.pathname, activeCharId])
}

export default function DiceOverlay() {
  const { t } = useTranslation()
  const { visible } = useOverlayVisibility()
  const [open, setOpen] = useState(false)
  const [pool, setPool] = useState<DicePool>({})

  const increment = useCallback((kind: DiceKind) => {
    haptic.light()
    setPool((p) => ({ ...p, [kind]: (p[kind] ?? 0) + 1 }))
  }, [])

  const toggleOpen = useCallback(() => {
    haptic.light()
    setOpen((o) => !o)
  }, [])

  if (!visible) return null

  return (
    <div className="fixed bottom-4 right-4 z-[55]">
      {/* Sidebar kind buttons — appears above the FAB */}
      <AnimatePresence>
        {open && (
          <m.div
            className="absolute bottom-full right-0 mb-2 flex flex-col-reverse gap-1.5"
            initial={{ opacity: 0, scaleY: 0.6, transformOrigin: 'bottom' }}
            animate={{ opacity: 1, scaleY: 1 }}
            exit={{ opacity: 0, scaleY: 0.6 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
          >
            {KINDS.map((kind, idx) => {
              const count = pool[kind] ?? 0
              return (
                <m.button
                  key={kind}
                  type="button"
                  onClick={() => increment(kind)}
                  className="relative w-12 h-12 rounded-2xl bg-dnd-surface-raised border border-dnd-border
                             flex items-center justify-center text-dnd-gold-bright
                             hover:border-dnd-gold/60 hover:shadow-halo-gold transition-[box-shadow,border-color]"
                  whileTap={{ scale: 0.9 }}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  aria-label={kind}
                >
                  <DiceIcon sides={SIDES_FOR[kind]} size={28} />
                  {count > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1
                                     rounded-full bg-dnd-crimson text-white text-[11px]
                                     font-bold font-mono flex items-center justify-center
                                     border border-dnd-surface-raised">
                      {count}
                    </span>
                  )}
                </m.button>
              )
            })}
          </m.div>
        )}
      </AnimatePresence>

      {/* FAB */}
      <m.button
        type="button"
        aria-label={open ? t('character.dice_overlay.close') : t('character.dice_overlay.open')}
        onClick={toggleOpen}
        className="w-14 h-14 rounded-full
                   bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright
                   border border-dnd-gold-dim shadow-halo-gold
                   flex items-center justify-center text-dnd-ink"
        whileTap={{ scale: 0.9 }}
        whileHover={{ scale: 1.05 }}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1, rotate: open ? 45 : 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      >
        <Dices size={26} />
      </m.button>
    </div>
  )
}
