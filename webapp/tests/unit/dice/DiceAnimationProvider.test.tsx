import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import type { SceneRequest } from '@/dice/DiceScene'

const scene = vi.hoisted(() => ({
  mode: 'ok' as 'ok' | 'throw' | 'slow',
  requests: [] as SceneRequest[],
  skipTokens: [] as number[],
}))

vi.mock('@/dice/DiceScene', async () => {
  const React = await import('react')
  return {
    default: function FakeScene({
      request,
      onMount,
      skipToken,
    }: {
      request: SceneRequest | null
      onMount?: () => void
      skipToken?: number
    }) {
      if (scene.mode === 'throw') throw new Error('Error creating WebGL context.')
      React.useEffect(() => {
        if (scene.mode !== 'slow') onMount?.()
      }, [])
      React.useEffect(() => {
        if (request) scene.requests.push(request)
      }, [request])
      React.useEffect(() => {
        if (skipToken) scene.skipTokens.push(skipToken)
      }, [skipToken])
      return null
    },
  }
})
vi.mock('@/dice/packs/DicePackProvider', () => ({
  DicePackProvider: ({ children }: { children: ReactNode }) => children,
}))
vi.mock('@/dice/preload', () => ({ schedulePreloadDiceScene: vi.fn() }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))

import DiceAnimationProvider from '@/dice/DiceAnimationProvider'
import { useDiceAnimation } from '@/dice/useDiceAnimation'

const wrapper = ({ children }: { children: ReactNode }) => (
  <DiceAnimationProvider>{children}</DiceAnimationProvider>
)

async function tick(ms = 0) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, ms))
  })
}

beforeEach(() => {
  scene.mode = 'ok'
  scene.requests.length = 0
  scene.skipTokens.length = 0
  vi.spyOn(console, 'error').mockImplementation(() => {})
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})

describe('DiceAnimationProvider', () => {
  it('still gives a complete result when the 3D scene cannot start', async () => {
    scene.mode = 'throw'
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let promise: ReturnType<typeof result.current.playAndCollect> = Promise.resolve([])
    await act(async () => {
      promise = result.current.playAndCollect([{ kind: 'd20', count: 2 }])
    })
    await tick(300)
    const out = await promise
    expect(out).toHaveLength(2)
    for (const die of out) {
      expect(die.groupIndex).toBe(0)
      expect(die.value).toBeGreaterThanOrEqual(1)
      expect(die.value).toBeLessThanOrEqual(20)
    }
  })

  it('does not try the scene again after it has failed once', async () => {
    scene.mode = 'throw'
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let promise: Promise<unknown[]> = Promise.resolve([])
    await act(async () => {
      promise = result.current.playAndCollect([{ kind: 'd6', count: 1 }])
    })
    await tick(300)
    await promise
    scene.mode = 'ok'
    await act(async () => {
      promise = result.current.playAndCollect([{ kind: 'd6', count: 3 }])
    })
    await tick(300)
    await expect(promise).resolves.toHaveLength(3)
    expect(scene.requests).toHaveLength(0)
  })

  it('plays overlapping rolls one after the other, and both complete', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let first: Promise<unknown[]> = Promise.resolve([])
    let second: Promise<unknown[]> = Promise.resolve([])
    await act(async () => {
      first = result.current.playAndCollect([{ kind: 'd20', count: 1 }])
      second = result.current.playAndCollect([{ kind: 'd6', count: 1 }])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    expect(scene.requests[0].groups[0].kind).toBe('d20')
    await act(async () => scene.requests[0].onComplete([{ groupIndex: 0, kind: 'd20', value: 11 }]))
    await tick(250)
    await waitFor(() => expect(scene.requests).toHaveLength(2))
    expect(scene.requests[1].groups[0].kind).toBe('d6')
    await act(async () => scene.requests[1].onComplete([{ groupIndex: 0, kind: 'd6', value: 4 }]))
    await tick(250)
    await expect(first).resolves.toEqual([{ groupIndex: 0, kind: 'd20', value: 11 }])
    await expect(second).resolves.toEqual([{ groupIndex: 0, kind: 'd6', value: 4 }])
  })

  it('animates at most 12 dice and completes the rest of a big pool', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let promise: Promise<Array<{ groupIndex: number; value: number }>> = Promise.resolve([])
    await act(async () => {
      promise = result.current.playAndCollect([
        { kind: 'd6', count: 30 },
        { kind: 'd20', count: 2 },
      ])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    const groups = scene.requests[0].groups
    expect(groups.reduce((s, g) => s + (g.count ?? 0), 0)).toBe(12)
    expect(groups[1].count).toBe(2)
    const shown = [
      ...Array.from({ length: groups[0].count! }, () => ({ groupIndex: 0, kind: 'd6' as const, value: 6 })),
      { groupIndex: 1, kind: 'd20' as const, value: 20 },
      { groupIndex: 1, kind: 'd20' as const, value: 19 },
    ]
    await act(async () => scene.requests[0].onComplete(shown))
    await tick(250)
    const out = await promise
    expect(out.filter((d) => d.groupIndex === 0)).toHaveLength(30)
    expect(out.filter((d) => d.groupIndex === 1).map((d) => d.value)).toEqual([20, 19])
  })

  it('completes pairs for d100 rolls beyond the animated dice', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let promise: Promise<unknown[]> = Promise.resolve([])
    await act(async () => {
      promise = result.current.playAndCollect([{ kind: 'd100', count: 10 }])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    const animated = scene.requests[0].groups[0].count!
    expect(animated).toBe(6)
    await act(async () =>
      scene.requests[0].onComplete(
        Array.from({ length: animated * 2 }, () => ({ groupIndex: 0, kind: 'd10' as const, value: 5 })),
      ),
    )
    await tick(250)
    await expect(promise).resolves.toHaveLength(20)
  })

  it('completes the roll when the scene reports no results', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let promise: Promise<unknown[]> = Promise.resolve([])
    await act(async () => {
      promise = result.current.playAndCollect([{ kind: 'd8', count: 3 }])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    await act(async () => scene.requests[0].onComplete([]))
    await tick(250)
    await expect(promise).resolves.toHaveLength(3)
  })

  it('shows the values as soon as the dice stop, instead of the skip hint', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    await act(async () => {
      void result.current.playAndCollect([
        { kind: 'd20', count: 2 },
        { kind: 'd100', count: 1 },
      ])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    const overlay = document.querySelector('[data-testid="dice-overlay"]') as HTMLElement
    expect(overlay.querySelector('[data-testid="dice-values"]')).toBeNull()
    await act(async () =>
      scene.requests[0].onSettled?.([
        { groupIndex: 0, kind: 'd20', value: 20 },
        { groupIndex: 0, kind: 'd20', value: 3 },
        { groupIndex: 1, kind: 'd10', value: 5 },
        { groupIndex: 1, kind: 'd10', value: 7 },
      ]),
    )
    expect(overlay.querySelector('[data-testid="dice-values"]')?.textContent).toBe('20 · 3 · 57')
  })

  it('renders above sheets and dialogs, which live directly on the body', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    await act(async () => {
      void result.current.playAndCollect([{ kind: 'd20', count: 1 }])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    const overlay = document.querySelector('[data-testid="dice-overlay"]') as HTMLElement
    expect(overlay.parentElement).toBe(document.body)
    expect(overlay.className).toContain('z-[90]')
  })

  it('keeps taps away from the page until the overlay has faded out', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    await act(async () => {
      void result.current.playAndCollect([{ kind: 'd20', count: 1 }])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    const overlay = document.querySelector('[data-testid="dice-overlay"]') as HTMLElement
    await act(async () => scene.requests[0].onComplete([{ groupIndex: 0, kind: 'd20', value: 5 }]))
    expect(overlay.style.opacity).toBe('0')
    expect(overlay.style.pointerEvents).toBe('auto')
    await tick(250)
    expect(overlay.style.pointerEvents).toBe('none')
  })

  it('stops waiting for a slow scene when the overlay is tapped', async () => {
    scene.mode = 'slow'
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    let promise: Promise<unknown[]> = Promise.resolve([])
    await act(async () => {
      promise = result.current.playAndCollect([{ kind: 'd6', count: 2 }])
    })
    await tick(20)
    const overlay = document.querySelector('[data-testid="dice-overlay"]') as HTMLElement
    await act(async () => overlay.click())
    await tick(250)
    await expect(promise).resolves.toHaveLength(2)
    expect(scene.requests).toHaveLength(0)
  })

  it('does not let a stuck scene hold the roll and the queue forever', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const { result } = renderHook(() => useDiceAnimation(), { wrapper })
      let promise: Promise<unknown[]> = Promise.resolve([])
      await act(async () => {
        promise = result.current.playAndCollect([{ kind: 'd8', count: 2 }])
      })
      await waitFor(() => expect(scene.requests).toHaveLength(1))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(31000)
      })
      await expect(promise).resolves.toHaveLength(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('asks the scene to skip when the overlay is tapped', async () => {
    const { result } = renderHook(() => useDiceAnimation(), { wrapper })
    await act(async () => {
      void result.current.playAndCollect([{ kind: 'd20', count: 1 }])
    })
    await waitFor(() => expect(scene.requests).toHaveLength(1))
    const overlay = document.querySelector('[data-testid="dice-overlay"]') as HTMLElement
    expect(overlay.style.pointerEvents).toBe('auto')
    await act(async () => overlay.click())
    expect(scene.skipTokens).toEqual([1])
  })
})
