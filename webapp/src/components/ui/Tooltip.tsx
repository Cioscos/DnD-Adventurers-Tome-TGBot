import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

let activeTooltipId: string | null = null
const subscribers = new Set<(id: string | null) => void>()

function setActive(id: string | null) {
  activeTooltipId = id
  subscribers.forEach(fn => fn(id))
}

interface TooltipProps {
  content: React.ReactNode
  children: React.ReactElement
  className?: string
}

export default function Tooltip({ content, children, className = '' }: TooltipProps) {
  const id = useId()
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLElement | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  useEffect(() => {
    const fn = (otherId: string | null) => {
      if (otherId !== id) setIsOpen(false)
    }
    subscribers.add(fn)
    return () => {
      subscribers.delete(fn)
      if (activeTooltipId === id) setActive(null)
    }
  }, [id])

  useLayoutEffect(() => {
    if (!isOpen) {
      setPos(null)
      return
    }
    const trigger = triggerRef.current
    const tip = tooltipRef.current
    if (!trigger || !tip) return
    const tRect = trigger.getBoundingClientRect()
    const tipRect = tip.getBoundingClientRect()
    const margin = 8
    const vw = window.innerWidth
    let top = tRect.top - tipRect.height - margin
    if (top < margin) {
      top = tRect.bottom + margin
    }
    let left = tRect.left + tRect.width / 2 - tipRect.width / 2
    if (left < margin) left = margin
    if (left + tipRect.width > vw - margin) left = vw - margin - tipRect.width
    setPos({ top, left })
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node
      if (triggerRef.current?.contains(target)) return
      if (tooltipRef.current?.contains(target)) return
      setIsOpen(false)
      if (activeTooltipId === id) setActive(null)
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('touchstart', handler)
    const onScroll = () => {
      setIsOpen(false)
      if (activeTooltipId === id) setActive(null)
    }
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('touchstart', handler)
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [isOpen, id])

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsOpen(prev => {
      const next = !prev
      setActive(next ? id : null)
      return next
    })
  }

  const trigger = (
    <span
      ref={(node) => { triggerRef.current = node }}
      onClick={handleToggle}
      className={`inline-flex ${className}`}
    >
      {children}
    </span>
  )

  return (
    <>
      {trigger}
      {isOpen && pos && createPortal(
        <div
          ref={tooltipRef}
          role="tooltip"
          className="fixed z-[100] max-w-[240px] rounded-lg border border-dnd-amber/70 bg-dnd-surface-raised
                     shadow-parchment-lg p-2 text-dnd-text font-body text-xs leading-snug pointer-events-none"
          style={{ top: pos.top, left: pos.left }}
        >
          {content}
        </div>,
        document.body
      )}
      {isOpen && !pos && createPortal(
        <div
          ref={tooltipRef}
          aria-hidden="true"
          className="fixed top-0 left-0 max-w-[240px] rounded-lg border border-dnd-amber/70 bg-dnd-surface-raised
                     shadow-parchment-lg p-2 text-dnd-text font-body text-xs leading-snug invisible pointer-events-none"
        >
          {content}
        </div>,
        document.body
      )}
    </>
  )
}
