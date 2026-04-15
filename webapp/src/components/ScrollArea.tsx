import { useRef, useState, useEffect } from 'react'

interface ScrollAreaProps {
  children: React.ReactNode
  className?: string
}

export default function ScrollArea({ children, className = '' }: ScrollAreaProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(false)
  const [showHint] = useState(() => !localStorage.getItem('scroll-hint-seen'))

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        setAtBottom(entry.isIntersecting)
        if (entry.isIntersecting && showHint) {
          localStorage.setItem('scroll-hint-seen', '1')
        }
      },
      { threshold: 0.1 }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [showHint])

  return (
    <div className={`relative ${className}`}>
      {children}
      <div ref={sentinelRef} className="h-1" />
      {!atBottom && (
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-[var(--dnd-bg)] to-transparent flex items-end justify-center pb-2">
          {showHint && (
            <span className="text-[10px] text-dnd-gold-dim opacity-70">↓ scorri</span>
          )}
        </div>
      )}
    </div>
  )
}
