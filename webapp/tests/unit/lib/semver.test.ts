import { describe, expect, it } from 'vitest'
import { compareSemver, isServerBehind } from '@/lib/semver'

describe('isServerBehind', () => {
  it('true quando il server ha major/minor minore', () => {
    expect(isServerBehind('2.24.0', '2.23.9')).toBe(true)
  })
  it('false a versioni uguali', () => {
    expect(isServerBehind('2.24.0', '2.24.0')).toBe(false)
  })
  it('ignora la patch', () => {
    expect(isServerBehind('2.24.1', '2.24.0')).toBe(false)
  })
  it('false con versione server ignota', () => {
    expect(isServerBehind('2.24.0', null)).toBe(false)
  })
  it('false se il server è più nuovo', () => {
    expect(isServerBehind('2.24.0', '3.0.0')).toBe(false)
  })
})

describe('compareSemver', () => {
  it('ordina', () => {
    expect(compareSemver('1.2.3', '1.2.4')).toBe(-1)
    expect(compareSemver('1.10.0', '1.9.0')).toBe(1)
    expect(compareSemver('1.0.0', '1.0.0')).toBe(0)
  })
})
