import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  playAndCollect: vi.fn(),
  animate3d: true,
  reduced: false,
}))

vi.mock('@/dice/useDiceAnimation', () => ({
  useDiceAnimation: () => ({ playAndCollect: mocks.playAndCollect }),
}))
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: mocks.animate3d }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => mocks.reduced }))

import { useAnimatedRoll } from '@/dice/useAnimatedRoll'

beforeEach(() => {
  mocks.playAndCollect.mockReset()
  mocks.animate3d = true
  mocks.reduced = false
})

describe('useAnimatedRoll', () => {
  it('returns the faces read by the 3D dice', async () => {
    mocks.playAndCollect.mockResolvedValue([
      { groupIndex: 0, kind: 'd8', value: 3 },
      { groupIndex: 0, kind: 'd8', value: 7 },
    ])
    const { result } = renderHook(() => useAnimatedRoll())
    await expect(result.current('d8', 2)).resolves.toEqual([3, 7])
    expect(mocks.playAndCollect).toHaveBeenCalledWith([{ kind: 'd8', count: 2 }])
  })

  it('leaves the roll to the server when the 3D dice are off', async () => {
    mocks.animate3d = false
    const { result } = renderHook(() => useAnimatedRoll())
    await expect(result.current('d20', 1)).resolves.toBeUndefined()
    expect(mocks.playAndCollect).not.toHaveBeenCalled()
  })

  it('leaves the roll to the server with reduced motion', async () => {
    mocks.reduced = true
    const { result } = renderHook(() => useAnimatedRoll())
    await expect(result.current('d20', 1)).resolves.toBeUndefined()
    expect(mocks.playAndCollect).not.toHaveBeenCalled()
  })

  it('leaves the roll to the server for a die that has no 3D model', async () => {
    const { result } = renderHook(() => useAnimatedRoll())
    await expect(result.current('d3', 1)).resolves.toBeUndefined()
    expect(mocks.playAndCollect).not.toHaveBeenCalled()
  })
})
