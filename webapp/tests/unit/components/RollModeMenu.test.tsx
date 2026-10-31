import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RollButton from '@/components/ui/RollButton'
import RollModeMenu from '@/components/ui/RollModeMenu'

const { info } = vi.hoisted(() => ({ info: vi.fn() }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const pointer = (x = 0, y = 0) => ({ clientX: x, clientY: y })

beforeEach(() => {
  localStorage.clear()
  info.mockReset()
})
afterEach(() => vi.useRealTimers())

describe('RollButton + RollModeMenu', () => {
  it('short tap rolls normal', () => {
    const onRoll = vi.fn()
    render(<RollButton onRoll={onRoll} ariaLabel="roll">x</RollButton>)
    const b = screen.getByLabelText('roll')
    fireEvent.pointerDown(b, pointer())
    fireEvent.pointerUp(b, pointer())
    expect(onRoll).toHaveBeenCalledWith('normal')
  })

  it('long press opens the menu with three options and Vantaggio rolls advantage', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    const onRoll = vi.fn()
    render(<RollButton onRoll={onRoll} ariaLabel="roll">x</RollButton>)
    const b = screen.getByLabelText('roll')
    fireEvent.pointerDown(b, pointer())
    act(() => { vi.advanceTimersByTime(460) })
    fireEvent.pointerUp(b, pointer())
    expect(onRoll).not.toHaveBeenCalled()
    expect(screen.getAllByRole('menuitem')).toHaveLength(3)
    fireEvent.click(screen.getByText('common.roll_mode.advantage'))
    expect(onRoll).toHaveBeenCalledWith('advantage')
    expect(screen.queryByRole('menuitem')).toBeNull()
  })

  it('shows the discoverability hint only once', async () => {
    const { unmount } = render(<RollButton onRoll={vi.fn()} ariaLabel="a">x</RollButton>)
    expect(info).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('dnd-hint-roll-mode')).toBe('1')
    unmount()
    render(<RollButton onRoll={vi.fn()} ariaLabel="a">x</RollButton>)
    expect(info).toHaveBeenCalledTimes(1)
    await userEvent.setup().keyboard('{Escape}')
  })

  it('opens above the anchor when there is no room below', () => {
    const h = window.innerHeight
    const anchor = { top: h - 50, bottom: h - 6, left: 0, right: 100 } as DOMRect
    render(<RollModeMenu anchor={anchor} onSelect={vi.fn()} onClose={vi.fn()} />)
    const top = parseFloat(screen.getByRole('menu').style.top)
    expect(top).toBeLessThan(anchor.top)
    expect(top).toBeGreaterThanOrEqual(8)
  })

  it('opens below the anchor when there is room', () => {
    const anchor = { top: 20, bottom: 64, left: 0, right: 100 } as DOMRect
    render(<RollModeMenu anchor={anchor} onSelect={vi.fn()} onClose={vi.fn()} />)
    expect(parseFloat(screen.getByRole('menu').style.top)).toBe(68)
  })
})
