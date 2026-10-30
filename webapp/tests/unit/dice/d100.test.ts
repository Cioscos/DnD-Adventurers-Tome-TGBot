import { describe, expect, it } from 'vitest'
import { d100FaceLabel, pairD100, rollValues } from '@/dice/d100'
import { needsOrientationMark } from '@/dice/numeralTexture'

describe('pairD100', () => {
  it('reads tens and units as a percentile', () => {
    expect(pairD100([3, 8])).toBe(38)
  })

  it('treats 10 as the digit 0', () => {
    expect(pairD100([10, 7])).toBe(7)
    expect(pairD100([4, 10])).toBe(40)
  })

  it('reads 00 + 0 as 100', () => {
    expect(pairD100([10, 10])).toBe(100)
  })
})

describe('rollValues', () => {
  it('turns each d100 pair into one percentile', () => {
    expect(rollValues('d100', [3, 8, 10, 10])).toEqual([38, 100])
  })

  it('leaves the other dice as they are', () => {
    expect(rollValues('d8', [3, 8])).toEqual([3, 8])
  })
})

describe('d100FaceLabel', () => {
  it('labels the tens die in tens', () => {
    expect(d100FaceLabel(3, 'tens')).toBe('30')
    expect(d100FaceLabel(10, 'tens')).toBe('00')
  })

  it('labels the units die with one digit', () => {
    expect(d100FaceLabel(7, 'units')).toBe('7')
    expect(d100FaceLabel(10, 'units')).toBe('0')
  })
})

describe('needsOrientationMark', () => {
  it.each(['6', '9', '66', '99', '60', '90'])('underlines %s, which reads differently upside down', (label) => {
    expect(needsOrientationMark(label)).toBe(true)
  })

  it.each(['1', '8', '16', '19', '00', '30', '69'])('leaves %s alone', (label) => {
    expect(needsOrientationMark(label)).toBe(false)
  })
})
