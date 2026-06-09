import { describe, it, expect, beforeEach } from 'vitest'
import { useDiceSettings } from '@/store/diceSettings'

beforeEach(() => useDiceSettings.setState({ animate3d: true, packId: 'default' }))

describe('useDiceSettings', () => {
  it('has the expected defaults', () => {
    const s = useDiceSettings.getState()
    expect(s.animate3d).toBe(true)
    expect(s.packId).toBe('default')
  })

  it('setAnimate3d and setPackId update the store', () => {
    useDiceSettings.getState().setAnimate3d(false)
    expect(useDiceSettings.getState().animate3d).toBe(false)
    useDiceSettings.getState().setPackId('runes')
    expect(useDiceSettings.getState().packId).toBe('runes')
  })
})
