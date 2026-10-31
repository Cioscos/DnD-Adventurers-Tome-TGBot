import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import type { RollMode } from '@/api/client'

const OPTIONS: { mode: RollMode; tone: string }[] = [
  { mode: 'advantage', tone: 'text-dnd-emerald-bright' },
  { mode: 'normal', tone: 'text-dnd-text' },
  { mode: 'disadvantage', tone: 'text-dnd-crimson-bright' },
]
const MENU_W = 176

/** Small popover anchored under the roll button: Vantaggio / Normale / Svantaggio. */
export default function RollModeMenu({
  anchor,
  onSelect,
  onClose,
}: {
  anchor: DOMRect
  onSelect: (mode: RollMode) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const left = Math.max(8, Math.min(anchor.right - MENU_W, window.innerWidth - MENU_W - 8))
  return createPortal(
    <div className="fixed inset-0 z-[70]" onClick={onClose} onContextMenu={(e) => e.preventDefault()}>
      <div
        role="menu"
        aria-label={t('common.roll_mode.title')}
        style={{ top: anchor.bottom + 4, left, width: MENU_W }}
        className="absolute rounded-xl border border-dnd-gold-dim/40 bg-dnd-surface-raised shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {OPTIONS.map(({ mode, tone }) => (
          <button
            key={mode}
            type="button"
            role="menuitem"
            onClick={() => onSelect(mode)}
            className={`w-full min-h-[44px] px-4 text-left text-sm font-body hover:bg-dnd-surface ${tone}`}
          >
            {t(`common.roll_mode.${mode}`)}
          </button>
        ))}
      </div>
    </div>,
    document.body,
  )
}
