import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Gift } from 'lucide-react'
import Button from '@/components/ui/Button'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import { spring } from '@/styles/motion'
import type { Reward } from '@/lib/rewardQueue'

interface Props {
  reward: Reward
  description?: string | null
  onDismiss: () => void
  onGoToInventory: () => void
}

export default function RewardPopup({ reward, description, onDismiss, onGoToInventory }: Props) {
  const { t } = useTranslation()

  // ESC + back/BackButton chiudono il popup (stack overlay condiviso).
  useOverlayDismiss(true, onDismiss)

  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [])

  return createPortal(
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-[60] flex items-center justify-center bg-[var(--dnd-overlay)] backdrop-blur-[6px] p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onDismiss}
      >
        <m.div
          className="w-full max-w-sm bg-dnd-surface-raised border border-dnd-gold rounded-2xl p-5 space-y-4"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={spring.swipe}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex flex-col items-center text-center gap-2">
            <Gift size={36} className="text-dnd-gold-bright" />
            <h2 className="text-base font-cinzel uppercase tracking-widest text-dnd-gold-bright">
              {t('session.reward.title')}
            </h2>
          </div>

          <div className="text-center space-y-1">
            <p className="font-display font-bold text-dnd-gold text-lg break-words">
              {reward.item_name}
            </p>
            {reward.item_quantity > 1 && (
              <p className="text-sm font-mono text-dnd-text-muted">
                ×{reward.item_quantity}
              </p>
            )}
            {description && (
              <p className="text-xs text-dnd-text-muted italic line-clamp-3 pt-1">
                {description}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2 pt-2">
            <Button variant="primary" fullWidth onClick={onGoToInventory}>
              {t('session.reward.cta_inventory')}
            </Button>
            <Button variant="secondary" fullWidth onClick={onDismiss}>
              {t('session.reward.cta_dismiss')}
            </Button>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>,
    document.body,
  )
}
