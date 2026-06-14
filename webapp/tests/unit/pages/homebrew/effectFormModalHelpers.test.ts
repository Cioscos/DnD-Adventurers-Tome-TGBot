import { describe, it, expect } from 'vitest'
import {
  isAmountValid,
  coerceAmount,
  coerceCompareValue,
  coerceListValue,
} from '@/pages/homebrew/sections/effectForm.utils'

describe('coerceListValue (F2-5: op "in" multi-value)', () => {
  it('splits a CSV string into a coerced array, dropping empty items', () => {
    expect(coerceListValue('fuoco, freddo, veleno')).toEqual(['fuoco', 'freddo', 'veleno'])
    expect(coerceListValue('1, 2, 3')).toEqual([1, 2, 3])
    expect(coerceListValue('true, false')).toEqual([true, false])
    expect(coerceListValue('a, , b,')).toEqual(['a', 'b'])
    expect(coerceListValue('')).toEqual([])
  })
})

describe('isAmountValid / coerceAmount with allowLevel (F2-7: N*level)', () => {
  it('accepts N*level only when allowLevel is true', () => {
    expect(isAmountValid('2*level', false, true)).toBe(true)
    expect(isAmountValid('-1*level', false, true)).toBe(true)
    expect(isAmountValid('2*LEVEL', false, true)).toBe(true) // case-insensitive (BE .lower())
    expect(isAmountValid('2*level', false, false)).toBe(false)
    expect(isAmountValid('2*level', false)).toBe(false) // default allowLevel=false
  })

  it('passes N*level through verbatim when allowed', () => {
    expect(coerceAmount('2*level', false, true)).toBe('2*level')
    expect(coerceAmount('-3*level', false, true)).toBe('-3*level')
  })

  it('still validates numbers, dice, $vars and max as before', () => {
    expect(isAmountValid('5', false)).toBe(true)
    expect(coerceAmount('5', false)).toBe(5)
    expect(isAmountValid('1d6', false)).toBe(true)
    expect(coerceAmount('1d6', false)).toBe('1d6')
    expect(isAmountValid('$blood', false)).toBe(true)
    expect(isAmountValid('max', true)).toBe(true)
    expect(coerceAmount('max', true)).toBe('max')
    expect(isAmountValid('', false)).toBe(false)
    expect(isAmountValid('pippo', false)).toBe(false)
  })
})

describe('coerceCompareValue', () => {
  it('coerces booleans and numbers, leaves plain strings', () => {
    expect(coerceCompareValue('true')).toBe(true)
    expect(coerceCompareValue('false')).toBe(false)
    expect(coerceCompareValue('42')).toBe(42)
    expect(coerceCompareValue('fuoco')).toBe('fuoco')
  })
})
