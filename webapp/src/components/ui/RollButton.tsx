import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLongPress } from '@/hooks/useLongPress'
import { useToast } from '@/hooks/useToast'
import { fireHaptic } from '@/lib/haptics'
import type { RollMode } from '@/api/client'
import RollModeMenu from './RollModeMenu'

const HINT_KEY = 'dnd-hint-roll-mode'

/** d20 roll trigger: tap = normal, long press (450 ms) = advantage/disadvantage menu.
 *  `askMode`: anche il tocco apre il menu (tiri salvezza: la modalità si sceglie sempre). */
export default function RollButton({
  onRoll,
  pending = false,
  disabled = false,
  ariaLabel,
  className = '',
  children,
  askMode = false,
}: {
  onRoll: (mode: RollMode) => void
  askMode?: boolean
  pending?: boolean
  disabled?: boolean
  ariaLabel: string
  className?: string
  children?: React.ReactNode
}) {
  const { t } = useTranslation()
  const toast = useToast()
  const ref = useRef<HTMLButtonElement>(null)
  const [anchor, setAnchor] = useState<DOMRect | null>(null)

  useEffect(() => {
    try {
      if (localStorage.getItem(HINT_KEY)) return
      localStorage.setItem(HINT_KEY, '1')
      toast.info(t('common.roll_mode.hint'), { hapticFeedback: false })
    } catch { /* storage or toast unavailable: the hint is optional */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openMenu = () => setAnchor(ref.current?.getBoundingClientRect() ?? null)
  const tap = () => (askMode ? openMenu() : onRoll('normal'))
  const press = useLongPress({
    thresholdMs: 450,
    onClick: tap,
    onLongPress: () => {
      fireHaptic('medium')
      openMenu()
    },
  })

  return (
    <>
      <button
        ref={ref}
        type="button"
        {...press}
        disabled={pending || disabled}
        aria-busy={pending}
        aria-label={ariaLabel}
        // Pointer/touch handlers do the rolling; a real click only matters for the keyboard (detail 0)
        // and must not bubble into a clickable parent row.
        onClick={(e) => {
          e.stopPropagation()
          if (e.detail === 0) tap()
        }}
        onContextMenu={(e) => e.preventDefault()}
        className={`select-none touch-manipulation disabled:opacity-40 ${className}`}
      >
        {children}
      </button>
      {anchor && (
        <RollModeMenu
          anchor={anchor}
          onClose={() => setAnchor(null)}
          onSelect={(mode) => {
            setAnchor(null)
            onRoll(mode)
          }}
        />
      )}
    </>
  )
}
