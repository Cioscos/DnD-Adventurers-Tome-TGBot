import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CharacterSwiper from '@/components/character/CharacterSwiper'

type DragInfo = { offset: { x: number }; velocity: { x: number } }
const { dragRef, setActiveScreenSpy, storeState } = vi.hoisted(() => ({
  dragRef: {} as { fn?: (e: unknown, info: DragInfo) => void },
  setActiveScreenSpy: vi.fn(),
  storeState: { activeScreen: 0 },
}))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const STRIP = new Set([
    'initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover',
    'drag', 'dragConstraints', 'dragElastic', 'dragDirectionLock', 'onDragEnd', 'style',
  ])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    if (typeof props.onDragEnd === 'function') dragRef.fn = props.onDragEnd as (e: unknown, info: DragInfo) => void
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!STRIP.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    useMotionValue: () => ({ get: () => 0, set: () => {} }),
    animate: () => ({ stop: () => {} }),
    useReducedMotion: () => true,
  }
})
vi.mock('@/store/characterStore', () => ({
  useCharacterStore: (sel: (s: { activeScreen: number; setActiveScreen: (n: number) => void }) => unknown) =>
    sel({ activeScreen: storeState.activeScreen, setActiveScreen: setActiveScreenSpy }),
}))
vi.mock('@/components/character/SwiperDots', async () => {
  const React = await import('react')
  return {
    default: (p: { onSelect: (i: number) => void }) =>
      React.createElement(
        'div',
        { 'data-testid': 'dots' },
        [0, 1, 2].map((i) => React.createElement('button', { key: i, 'data-testid': `dot-${i}`, onClick: () => p.onSelect(i) })),
      ),
  }
})

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  })
})
afterEach(() => {
  setActiveScreenSpy.mockReset()
  storeState.activeScreen = 0
})

describe('CharacterSwiper', () => {
  it('renders the three screens and the dots', () => {
    render(<CharacterSwiper hero={<div>HERO</div>} equipment={<div>EQUIP</div>} menu={<div>MENU</div>} />)
    expect(screen.getByText('HERO')).toBeInTheDocument()
    expect(screen.getByText('EQUIP')).toBeInTheDocument()
    expect(screen.getByText('MENU')).toBeInTheDocument()
    expect(screen.getByTestId('dots')).toBeInTheDocument()
  })

  it('selecting a dot sets the active screen', async () => {
    render(<CharacterSwiper hero={<div>H</div>} equipment={<div>E</div>} menu={<div>M</div>} />)
    await userEvent.click(screen.getByTestId('dot-2'))
    expect(setActiveScreenSpy).toHaveBeenCalledWith(2)
  })

  it('a leftward drag past the threshold advances to the next screen', () => {
    render(<CharacterSwiper hero={<div>H</div>} equipment={<div>E</div>} menu={<div>M</div>} />)
    dragRef.fn?.(null, { offset: { x: -200 }, velocity: { x: 0 } })
    expect(setActiveScreenSpy).toHaveBeenCalledWith(1)
  })

  it('a rightward drag goes back to the previous screen', () => {
    storeState.activeScreen = 1
    render(<CharacterSwiper hero={<div>H</div>} equipment={<div>E</div>} menu={<div>M</div>} />)
    dragRef.fn?.(null, { offset: { x: 200 }, velocity: { x: 0 } })
    expect(setActiveScreenSpy).toHaveBeenCalledWith(0)
  })

  it('a tap (tiny offset) never changes the screen, even on a velocity spike', () => {
    render(<CharacterSwiper hero={<div>H</div>} equipment={<div>E</div>} menu={<div>M</div>} />)
    dragRef.fn?.(null, { offset: { x: -3 }, velocity: { x: -2000 } })
    expect(setActiveScreenSpy).not.toHaveBeenCalled()
  })
})
