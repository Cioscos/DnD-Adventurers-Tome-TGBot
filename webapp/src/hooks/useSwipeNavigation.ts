import { useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useModal } from '@/components/ModalProvider'
import { haptic } from '@/auth/telegram'

const PAGE_GROUPS: Record<string, string[]> = {
  combat: ['hp', 'ac', 'saves'],
  magic: ['spells', 'slots'],
  skills: ['stats', 'skills', 'abilities'],
  equipment: ['inventory', 'currency'],
  character: ['identity', 'class', 'xp', 'conditions'],
  tools: ['dice', 'notes', 'maps', 'history'],
}

export function getGroupInfo(group?: string, page?: string) {
  if (!group || !page) return null
  const pages = PAGE_GROUPS[group]
  if (!pages) return null
  const index = pages.indexOf(page)
  if (index === -1) return null
  return { pages, index, total: pages.length }
}

export function useSwipeNavigation(group?: string, page?: string) {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const { isModalOpen } = useModal()
  const touchRef = useRef({ startX: 0, startY: 0, swiping: false })
  const contentRef = useRef<HTMLDivElement>(null)

  const info = getGroupInfo(group, page)

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (isModalOpen || !info) return
    const touch = e.touches[0]
    touchRef.current = { startX: touch.clientX, startY: touch.clientY, swiping: false }
  }, [isModalOpen, info])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (isModalOpen || !info) return
    const touch = e.touches[0]
    const deltaX = touch.clientX - touchRef.current.startX
    const deltaY = touch.clientY - touchRef.current.startY

    // Only engage if horizontal intent dominates
    if (!touchRef.current.swiping) {
      if (Math.abs(deltaX) > Math.abs(deltaY) * 1.5 && Math.abs(deltaX) > 10) {
        touchRef.current.swiping = true
      } else {
        return
      }
    }

    if (contentRef.current) {
      // Rubber-band at edges
      const atEdge = (deltaX > 0 && info.index === 0) || (deltaX < 0 && info.index === info.total - 1)
      const translate = atEdge ? deltaX * 0.3 : deltaX
      contentRef.current.style.transform = `translateX(${translate}px)`
      contentRef.current.style.transition = 'none'
    }
  }, [isModalOpen, info])

  const onTouchEnd = useCallback(() => {
    if (!info || !touchRef.current.swiping) {
      if (contentRef.current) {
        contentRef.current.style.transform = ''
        contentRef.current.style.transition = ''
      }
      return
    }

    const deltaX = (contentRef.current?.style.transform
      ? parseFloat(contentRef.current.style.transform.replace('translateX(', '').replace('px)', ''))
      : 0)

    if (contentRef.current) {
      contentRef.current.style.transition = 'transform 150ms ease'
      contentRef.current.style.transform = ''
    }

    if (Math.abs(deltaX) > 80) {
      const direction = deltaX > 0 ? -1 : 1
      const nextIndex = info.index + direction
      if (nextIndex >= 0 && nextIndex < info.total) {
        haptic.light()
        navigate(`/char/${id}/${info.pages[nextIndex]}`, { replace: true })
      }
    }

    touchRef.current.swiping = false
  }, [info, navigate, id])

  return {
    contentRef,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    currentIndex: info?.index ?? 0,
    total: info?.total ?? 1,
  }
}
