import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

const mocks = vi.hoisted(() => ({
  result: vi.fn(async () => ({ notation: 'x', rolls: [], total: 0 })),
  playAndCollect: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: { dice: { result: mocks.result } } }))
vi.mock('@/dice/useDiceAnimation', () => ({
  useDiceAnimation: () => ({ playAndCollect: mocks.playAndCollect, isPlaying: false }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))

import { useRollAndPersist } from '@/dice/useRollAndPersist'

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
)

const d10 = (value: number) => ({ groupIndex: 0, kind: 'd10' as const, value })

beforeEach(() => {
  mocks.result.mockClear()
  mocks.playAndCollect.mockReset()
})

describe('useRollAndPersist', () => {
  it('saves the same d100 total that it shows', async () => {
    mocks.playAndCollect.mockResolvedValue([d10(3), d10(8)])
    const { result } = renderHook(() => useRollAndPersist(1), { wrapper })
    let groups: Awaited<ReturnType<typeof result.current.roll>> = []
    await act(async () => {
      groups = await result.current.roll([{ kind: 'd100', count: 1 }])
    })
    expect(groups[0].total).toBe(38)
    expect(mocks.result).toHaveBeenCalledWith(1, expect.objectContaining({ total: 38, notation: '1d100' }))
  })

  it('asks for one d100 per roll and sums every pair', async () => {
    mocks.playAndCollect.mockResolvedValue([d10(1), d10(2), d10(3), d10(4), d10(10), d10(10)])
    const { result } = renderHook(() => useRollAndPersist(1), { wrapper })
    let groups: Awaited<ReturnType<typeof result.current.roll>> = []
    await act(async () => {
      groups = await result.current.roll([{ kind: 'd100', count: 3 }])
    })
    expect(mocks.playAndCollect).toHaveBeenCalledWith([{ kind: 'd100', tint: undefined, count: 3 }])
    expect(groups[0].total).toBe(12 + 34 + 100)
    expect(mocks.result).toHaveBeenCalledWith(1, expect.objectContaining({ total: 146, notation: '3d100' }))
  })

  it('leaves the total to the server for plain dice', async () => {
    mocks.playAndCollect.mockResolvedValue([{ groupIndex: 0, kind: 'd6', value: 5 }])
    const { result } = renderHook(() => useRollAndPersist(1), { wrapper })
    await act(async () => {
      await result.current.roll([{ kind: 'd6', count: 1 }])
    })
    expect(mocks.result).toHaveBeenCalledWith(1, expect.objectContaining({ total: null, notation: null }))
  })

  it('reports pending for the whole animation, not only while saving', async () => {
    let finish: (v: unknown[]) => void = () => {}
    mocks.playAndCollect.mockReturnValue(new Promise((r) => (finish = r)))
    const { result } = renderHook(() => useRollAndPersist(1), { wrapper })
    let rolling: Promise<unknown> = Promise.resolve()
    act(() => {
      rolling = result.current.roll([{ kind: 'd20', count: 1 }])
    })
    await waitFor(() => expect(result.current.isPending).toBe(true))
    expect(mocks.result).not.toHaveBeenCalled()
    await act(async () => {
      finish([{ groupIndex: 0, kind: 'd20', value: 7 }])
      await rolling
    })
    await waitFor(() => expect(result.current.isPending).toBe(false))
  })
})
