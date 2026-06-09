import { describe, it, expect, vi, beforeEach } from 'vitest'
import confetti from 'canvas-confetti'
import { fireLevelUpConfetti } from '@/lib/celebrate'

vi.mock('canvas-confetti', () => ({ default: vi.fn() }))

describe('fireLevelUpConfetti', () => {
  beforeEach(() => vi.mocked(confetti).mockClear())

  it('fires two confetti bursts from the two bottom corners', () => {
    fireLevelUpConfetti()
    expect(confetti).toHaveBeenCalledTimes(2)
    const calls = vi.mocked(confetti).mock.calls
    expect(calls[0][0]).toMatchObject({ origin: { x: 0.05, y: 0.9 }, angle: 60 })
    expect(calls[1][0]).toMatchObject({ origin: { x: 0.95, y: 0.9 }, angle: 120 })
  })
})
