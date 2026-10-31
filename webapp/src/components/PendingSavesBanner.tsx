import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Dices } from 'lucide-react'
import { haptic } from '@/auth/telegram'
import { usePendingSaves } from '@/hooks/usePendingSaves'
import Pressable from '@/components/ui/Pressable'
import SaveRollSheet from '@/components/SaveRollSheet'

/** Always-on strip while the character has repeated saving throws to roll. */
export default function PendingSavesBanner({ charId }: { charId: number }) {
  const { t } = useTranslation()
  const { saves, isMyTurn } = usePendingSaves(charId)
  const [open, setOpen] = useState(false)
  const pending = saves.filter((s) => s.status === 'pending')
  const strong = isMyTurn && pending.length > 0

  const wasStrong = useRef(false)
  useEffect(() => {
    if (strong && !wasStrong.current) haptic.warning()
    wasStrong.current = strong
  }, [strong])

  const first = pending[0] ?? saves[0]
  const cond = first ? t(`character.conditions.${first.slug}`, { defaultValue: first.slug }) : ''
  const label = !first
    ? ''
    : pending.length > 1
      ? t('pendingSaves.banner_many', { count: pending.length })
      : pending.length === 1
        ? t('pendingSaves.banner_one', { ability: t(`character.stats.${first.ability}`), dc: first.dc, condition: cond })
        : t('pendingSaves.banner_failed', { condition: cond })

  const onTap = () => {
    haptic.light()
    setOpen(true)
  }

  return (
    <>
      {saves.length > 0 && <m.div
        initial={{ y: -8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        data-testid="pending-saves-banner"
        data-strong={strong}
        className="sticky top-0 z-30 w-full"
      >
        <Pressable
          onClick={onTap}
          className={`relative w-full min-h-[44px] flex items-center gap-2 px-3 py-2 border-y backdrop-blur-sm shadow-parchment-md text-left ${
            strong
              ? 'bg-dnd-crimson/25 border-dnd-crimson/70 text-dnd-crimson-bright'
              : 'bg-dnd-amber/15 border-dnd-amber/60 text-dnd-amber'
          }`}
        >
          {strong && (
            <m.span
              aria-hidden
              className="absolute inset-0 shadow-halo-danger pointer-events-none"
              animate={{ opacity: [0.35, 1, 0.35] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
          <Dices size={16} className="shrink-0" />
          <span className="flex-1 min-w-0 text-sm font-display font-bold truncate tabular-nums">{label}</span>
          {strong && (
            <span className="shrink-0 text-xs uppercase tracking-widest font-cinzel">{t('pendingSaves.your_turn')}</span>
          )}
        </Pressable>
      </m.div>}
      {open && <SaveRollSheet charId={charId} saves={[...pending, ...saves.filter((s) => s.status !== 'pending')]} onClose={() => setOpen(false)} />}
    </>
  )
}
