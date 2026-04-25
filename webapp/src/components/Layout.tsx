import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft } from 'lucide-react'
import { m } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

interface LayoutProps {
  title: string
  children: React.ReactNode
  /** @deprecated Kept for compatibility — Layout always uses history.back() now. */
  backTo?: string
  group?: string
  page?: string
}

export default function Layout({ title, children, group, page }: LayoutProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const swipe = useSwipeNavigation(group, page)
  const info = getGroupInfo(group, page)
  const { id } = useParams<{ id: string }>()

  const handleBack = () => {
    navigate(-1)
  }

  return (
    <div
      className="w-full flex flex-col bg-dnd-bg"
      style={{ height: 'var(--tg-vh, 100vh)' }}
    >
      <m.header
        className="shrink-0 z-10 flex flex-col px-4 py-3 pt-safe
                    bg-dnd-surface-raised/95 backdrop-blur-sm
                    border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <div className="flex items-center gap-3">
          <m.button
            onClick={handleBack}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
            aria-label="Indietro"
            whileTap={{ scale: 0.9 }}
            whileHover={{ boxShadow: 'var(--halo-gold)' }}
          >
            <ChevronLeft size={20} className="text-dnd-gold-bright" />
          </m.button>
          <h1 className="text-lg font-bold font-display text-dnd-gold-bright truncate flex-1"
              style={{ textShadow: '0 1px 4px var(--dnd-gold-glow)' }}>
            {title}
          </h1>
        </div>
        {info && (() => {
          const prevKey = info.index > 0 ? info.pages[info.index - 1] : null
          const currKey = info.pages[info.index]
          const nextKey = info.index < info.total - 1 ? info.pages[info.index + 1] : null

          const goToPrev = () => {
            if (prevKey && id) {
              haptic.light()
              navigate(`/char/${id}/${prevKey}`, { replace: true })
            }
          }
          const goToNext = () => {
            if (nextKey && id) {
              haptic.light()
              navigate(`/char/${id}/${nextKey}`, { replace: true })
            }
          }

          return (
            <div className="flex items-center justify-center gap-1.5 mt-2 text-xs overflow-x-auto scrollbar-hide font-body">
              {prevKey && (
                <>
                  <m.button
                    type="button"
                    onClick={goToPrev}
                    whileTap={{ scale: 0.95 }}
                    aria-label={t('layout.nav.go_to', { page: t(`character.menu.${prevKey}`) })}
                    className="text-dnd-text-muted opacity-70 whitespace-nowrap px-1.5 py-0.5 rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
                    style={{ filter: 'blur(0.5px)' }}
                  >
                    {t(`character.menu.${prevKey}`)}
                  </m.button>
                  <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
                </>
              )}
              <span className="text-dnd-gold-bright font-semibold whitespace-nowrap">
                {t(`character.menu.${currKey}`)}
              </span>
              {nextKey && (
                <>
                  <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
                  <m.button
                    type="button"
                    onClick={goToNext}
                    whileTap={{ scale: 0.95 }}
                    aria-label={t('layout.nav.go_to', { page: t(`character.menu.${nextKey}`) })}
                    className="text-dnd-text-muted opacity-70 whitespace-nowrap px-1.5 py-0.5 rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
                    style={{ filter: 'blur(0.5px)' }}
                  >
                    {t(`character.menu.${nextKey}`)}
                  </m.button>
                </>
              )}
            </div>
          )
        })()}
      </m.header>

      <main
        ref={swipe.contentRef}
        className="flex-1 min-w-0 overflow-y-auto p-4 space-y-3 pb-safe animate-fade-in"
        onTouchStart={swipe.onTouchStart}
        onTouchMove={swipe.onTouchMove}
        onTouchEnd={swipe.onTouchEnd}
      >
        {children}
      </main>
    </div>
  )
}
