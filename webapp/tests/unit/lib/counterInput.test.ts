import { describe, it, expect } from 'vitest'
import { parseCounterInput } from '@/lib/counterInput'

describe('parseCounterInput', () => {
  it('accetta interi nel range e clampa', () => {
    expect(parseCounterInput('150', 200)).toBe(150)
    expect(parseCounterInput('999', 200)).toBe(200)
    expect(parseCounterInput('-3', 200)).toBe(0)
  })
  it('senza max clampa solo a >= 0', () => {
    expect(parseCounterInput('42', null)).toBe(42)
    expect(parseCounterInput('-1', null)).toBe(0)
  })
  it('rifiuta input non numerici o non interi', () => {
    expect(parseCounterInput('', 10)).toBeNull()
    expect(parseCounterInput('abc', 10)).toBeNull()
    expect(parseCounterInput('3.5', 10)).toBeNull()
  })
})
