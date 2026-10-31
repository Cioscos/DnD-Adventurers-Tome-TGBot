import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLongPress } from '@/hooks/useLongPress'
import { useToast } from '@/hooks/useToast'
import { fireHaptic } from '@/lib/haptics'
import type { RollMode } from '@/api/client'
import RollModeMenu from './RollModeMenu'

const HINT_KEY = 'dnd-hint-roll-mode'

/** d20 roll trigger: tap = normal, long press (450 ms) = advantage/disadvantage menu. */
export default function RollButton({
  onRoll,
  pending = false,
  ariaLabel,
  className = '',
  children,
}: {
  onRoll: (mode: RollMode) => void
  pending?: boolean
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

  const press = useLongPress({
    thresholdMs: 450,
    onClick: () => onRoll('normal'),
    onLongPress: () => {
      fireHaptic('medium')
      setAnchor(ref.current?.getBoundingClientRect() ?? null)
    },
  })

  return (
    <>
      <button
        ref={ref}
        type="button"
        {...press}
        disabled={pending}
        aria-busy={pending}
        aria-label={ariaLabel}
        // Pointer/touch handlers do the rolling; a real click only matters for the keyboard (detail 0)
        // and must not bubble into a clickable parent row.
        onClick={(e) => {
          e.stopPropagation()
          if (e.detail === 0) onRoll('normal')
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
