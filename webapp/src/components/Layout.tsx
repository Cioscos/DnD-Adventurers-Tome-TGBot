import { useNavigate } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'

interface LayoutProps {
  title: string
  children: React.ReactNode
  backTo?: string
  group?: string
  page?: string
}

export default function Layout({ title, children, backTo, group, page }: LayoutProps) {
  const navigate = useNavigate()
  const swipe = useSwipeNavigation(group, page)
  const info = getGroupInfo(group, page)

  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  return (
    <div className="min-h-screen w-full flex flex-col bg-dnd-bg">
      <header
        className="sticky top-0 z-10 flex flex-col px-4 py-3 pt-safe
                    bg-dnd-surface-elevated border-b border-dnd-gold-dim/30"
      >
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="p-1 rounded-lg active:opacity-60 transition-opacity"
            aria-label="Indietro"
          >
            <ChevronLeft size={20} className="text-dnd-gold" />
          </button>
          <h1 className="text-lg font-bold font-cinzel text-dnd-gold truncate flex-1">
            {title}
          </h1>
        </div>
        {info && (
          <div className="flex justify-center gap-1.5 mt-2">
            {Array.from({ length: info.total }).map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === info.index ? 'bg-dnd-gold' : 'bg-dnd-gold-dim/40'
                }`}
              />
            ))}
          </div>
        )}
      </header>

      <main
        ref={swipe.contentRef}
        className="flex-1 min-w-0 p-4 space-y-3 pb-safe animate-fade-in"
        onTouchStart={swipe.onTouchStart}
        onTouchMove={swipe.onTouchMove}
        onTouchEnd={swipe.onTouchEnd}
      >
        {children}
      </main>
    </div>
  )
}
