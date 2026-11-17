import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useD20Roll, d20Arg, d20Count } from '@/hooks/useD20Roll'

const { playAndCollect, settings } = vi.hoisted(() => ({
  playAndCollect: vi.fn(),
  settings: { animate3d: true },
}))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect }) }))
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel(settings),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))

beforeEach(() => {
  playAndCollect.mockReset()
  settings.animate3d = true
})

describe('useD20Roll', () => {
  it('returns two faces for advantage', async () => {
    playAndCollect.mockResolvedValue([
      { groupIndex: 0, kind: 'd20', value: 7 },
      { groupIndex: 0, kind: 'd20', value: 15 },
    ])
    const { result } = renderHook(() => useD20Roll())
    await expect(result.current('advantage')).resolves.toEqual([7, 15])
    expect(playAndCollect).toHaveBeenCalledWith([{ kind: 'd20', count: 2 }])
  })

  it('returns one face for normal', async () => {
    playAndCollect.mockResolvedValue([{ groupIndex: 0, kind: 'd20', value: 12 }])
    const { result } = renderHook(() => useD20Roll())
    await expect(result.current('normal')).resolves.toEqual([12])
    expect(playAndCollect).toHaveBeenCalledWith([{ kind: 'd20', count: 1 }])
  })

  it('returns undefined when 3D is off (server rolls)', async () => {
    settings.animate3d = false
    const { result } = renderHook(() => useD20Roll())
    await expect(result.current('disadvantage')).resolves.toBeUndefined()
    expect(playAndCollect).not.toHaveBeenCalled()
  })
})

describe('d20Arg', () => {
  it('keeps the legacy single die for normal rolls', () => {
    expect(d20Arg('normal', [9])).toBe(9)
    expect(d20Arg('normal', undefined)).toBeUndefined()
  })
  it('sends dice and mode otherwise', () => {
    expect(d20Arg('advantage', [3, 8])).toEqual({ dice: [3, 8], mode: 'advantage' })
    expect(d20Arg('disadvantage', undefined)).toEqual({ dice: undefined, mode: 'disadvantage' })
  })
})

describe('d20Count (U16: tutti i d20 che contano si vedono)', () => {
  const choice = (modes: ('advantage' | 'disadvantage')[]) => ({ options: ['x'], option_inputs: {}, modes })
  it('rolls two dice when a chosen option gives advantage or disadvantage', () => {
    expect(d20Count('normal', choice(['advantage']))).toBe(2)
    expect(d20Count('normal', choice(['disadvantage']))).toBe(2)
  })
  it('rolls one die when the modes cancel out', () => {
    expect(d20Count('advantage', choice(['disadvantage']))).toBe(1)
    expect(d20Count('normal')).toBe(1)
  })
  it('animates the option dice', async () => {
    playAndCollect.mockResolvedValue([])
    const { result } = renderHook(() => useD20Roll())
    await result.current('normal', choice(['advantage']))
    expect(playAndCollect).toHaveBeenCalledWith([{ kind: 'd20', count: 2 }])
  })
})
