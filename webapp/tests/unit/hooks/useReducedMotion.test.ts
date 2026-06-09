import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useReducedMotion } from '@/hooks/useReducedMotion'

const { reduced } = vi.hoisted(() => ({ reduced: { value: false as boolean | null } }))
vi.mock('framer-motion', () => ({ useReducedMotion: () => reduced.value }))

describe('useReducedMotion', () => {
  it('reflects the framer reduced-motion value', () => {
    reduced.value = true
    expect(renderHook(() => useReducedMotion()).result.current).toBe(true)
    reduced.value = false
    expect(renderHook(() => useReducedMotion()).result.current).toBe(false)
  })

  it('coerces a null framer result to false', () => {
    reduced.value = null
    expect(renderHook(() => useReducedMotion()).result.current).toBe(false)
  })
})
