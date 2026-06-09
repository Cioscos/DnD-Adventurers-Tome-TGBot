import { describe, it, expect, beforeEach } from 'vitest'
import {
  useUnitSettings,
  unitLabel,
  feetToDisplay,
  displayToFeet,
  formatLength,
  oppositeSystem,
  weightUnitLabel,
  lbToDisplay,
  displayToLb,
  formatWeightValue,
  formatWeight,
} from '@/store/unitSettings'

// The grid factors are deliberate clean tabletop ratios (5 ft = 1.5 m, 1 lb = 0.5 kg),
// not real-world conversions — round-trips must stay clean.
describe('unitSettings length helpers', () => {
  it('labels and converts feet ⇄ metres on the D&D grid factor', () => {
    expect(unitLabel('imperial')).toBe('ft')
    expect(unitLabel('metric')).toBe('m')

    expect(feetToDisplay(30, 'imperial')).toBe(30)
    expect(feetToDisplay(30, 'metric')).toBe(9)
    expect(feetToDisplay(5, 'metric')).toBe(1.5)

    // round-trip back to canonical integer feet
    expect(displayToFeet(9, 'metric')).toBe(30)
    expect(displayToFeet(1.5, 'metric')).toBe(5)
    expect(displayToFeet(30, 'imperial')).toBe(30)
  })

  it('formats lengths and strips the trailing .0', () => {
    expect(formatLength(30, 'imperial')).toBe('30 ft')
    expect(formatLength(30, 'metric')).toBe('9 m')
    expect(formatLength(5, 'metric')).toBe('1.5 m')
  })

  it('flips the system', () => {
    expect(oppositeSystem('imperial')).toBe('metric')
    expect(oppositeSystem('metric')).toBe('imperial')
  })
})

describe('unitSettings weight helpers', () => {
  it('labels and converts pounds ⇄ kilograms', () => {
    expect(weightUnitLabel('imperial')).toBe('lb')
    expect(weightUnitLabel('metric')).toBe('kg')

    // STR 15 carry capacity = 225 lb → 112.5 kg
    expect(lbToDisplay(225, 'imperial')).toBe(225)
    expect(lbToDisplay(225, 'metric')).toBe(112.5)
    expect(displayToLb(112.5, 'metric')).toBe(225)
    expect(displayToLb(225, 'imperial')).toBe(225)
  })

  it('formats weights with and without the unit suffix', () => {
    expect(formatWeightValue(225, 'imperial')).toBe('225')
    expect(formatWeightValue(225, 'metric')).toBe('112.5')
    expect(formatWeight(225, 'imperial')).toBe('225 lb')
    expect(formatWeight(225, 'metric')).toBe('112.5 kg')
  })
})

describe('useUnitSettings store', () => {
  beforeEach(() => {
    useUnitSettings.setState({ system: 'imperial' })
  })

  it('defaults to imperial and toggles via setSystem', () => {
    expect(useUnitSettings.getState().system).toBe('imperial')
    useUnitSettings.getState().setSystem('metric')
    expect(useUnitSettings.getState().system).toBe('metric')
  })
})
