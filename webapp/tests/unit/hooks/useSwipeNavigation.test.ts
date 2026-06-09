import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { getGroupInfo, useSwipeNavigation } from '@/hooks/useSwipeNavigation'

vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn(), useParams: () => ({ id: '7' }) }))
vi.mock('@/components/modalContext', () => ({ useModal: () => ({ isModalOpen: false }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

describe('getGroupInfo', () => {
  it('resolves a page within its group to {index, total}', () => {
    expect(getGroupInfo('combat', 'hp')).toEqual({ pages: ['hp', 'ac', 'saves', 'actions'], index: 0, total: 4 })
    expect(getGroupInfo('combat', 'saves')?.index).toBe(2)
  })

  it('returns null for an unknown group, page, or missing args', () => {
    expect(getGroupInfo('nope', 'hp')).toBeNull()
    expect(getGroupInfo('combat', 'nope')).toBeNull()
    expect(getGroupInfo(undefined, undefined)).toBeNull()
  })
})

describe('useSwipeNavigation', () => {
  it('exposes the current index and total for the group', () => {
    const { result } = renderHook(() => useSwipeNavigation('magic', 'slots'))
    expect(result.current.currentIndex).toBe(1)
    expect(result.current.total).toBe(2)
  })

  it('falls back to a single-page model for an unknown group', () => {
    const { result } = renderHook(() => useSwipeNavigation('nope', 'x'))
    expect(result.current.currentIndex).toBe(0)
    expect(result.current.total).toBe(1)
  })
})
