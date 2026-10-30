import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { getGroupInfo, useSwipeNavigation } from '@/hooks/useSwipeNavigation'

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))

vi.mock('react-router-dom', () => ({ useNavigate: () => navigateSpy, useParams: () => ({ id: '7' }) }))
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

describe('useSwipeNavigation — rilascio del gesto', () => {
  const WIDTH = 400

  beforeEach(() => {
    // performance incluso: la velocità del gesto si misura con performance.now().
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] })
    navigateSpy.mockReset()
  })
  afterEach(() => vi.useRealTimers())

  const setup = (page = 'ac') => {
    const hook = renderHook(() => useSwipeNavigation('combat', page))
    const content = document.createElement('div')
    Object.defineProperty(content, 'offsetWidth', { value: WIDTH })
    ;(hook.result.current.contentRef as { current: HTMLDivElement | null }).current = content
    const at = (x: number) => ({ touches: [{ clientX: x, clientY: 100 }], target: content }) as unknown as React.TouchEvent
    return { hook, content, at }
  }

  /** Trascina da 380 a `to` in 10 passi distanziati di `stepMs`, poi tiene fermo `holdMs`. */
  const drag = ({ hook, at }: ReturnType<typeof setup>, to: number, stepMs: number, holdMs = 0) => {
    act(() => hook.result.current.onTouchStart(at(380)))
    for (let i = 1; i <= 10; i++) {
      act(() => { vi.advanceTimersByTime(stepMs) })
      act(() => hook.result.current.onTouchMove(at(380 + ((to - 380) * i) / 10)))
    }
    act(() => { vi.advanceTimersByTime(holdMs) })
    act(() => hook.result.current.onTouchEnd())
    act(() => { vi.advanceTimersByTime(400) })
  }

  it('un trascinamento lento e corto torna indietro, senza navigare', () => {
    const s = setup()
    drag(s, 280, 50)
    expect(navigateSpy).not.toHaveBeenCalled()
    expect(s.content.style.transform).toBe('')
  })

  it('anche un gesto veloce non naviga se il dito si ferma prima di alzarsi', () => {
    const s = setup()
    drag(s, 280, 5, 200)
    expect(navigateSpy).not.toHaveBeenCalled()
  })

  it('oltre metà schermo naviga anche se lento', () => {
    const s = setup()
    drag(s, 150, 50, 200)
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/saves', { replace: true })
  })

  it('un flick breve ma veloce naviga', () => {
    const s = setup()
    drag(s, 300, 5)
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/saves', { replace: true })
  })

  it('trascinando verso destra va alla pagina precedente', () => {
    const s = setup()
    act(() => s.hook.result.current.onTouchStart(s.at(20)))
    for (let i = 1; i <= 10; i++) {
      act(() => { vi.advanceTimersByTime(50) })
      act(() => s.hook.result.current.onTouchMove(s.at(20 + 25 * i)))
    }
    act(() => s.hook.result.current.onTouchEnd())
    act(() => { vi.advanceTimersByTime(400) })
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/hp', { replace: true })
  })

  it('oltre il bordo del gruppo non naviga', () => {
    const s = setup('actions')
    drag(s, 100, 5)
    expect(navigateSpy).not.toHaveBeenCalled()
  })
})
