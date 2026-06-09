import { describe, it, expect, beforeEach } from 'vitest'
import { useThemeSettings } from '@/store/themeSettings'

beforeEach(() => useThemeSettings.setState({ mode: 'auto' }))

describe('useThemeSettings', () => {
  it('defaults to auto mode', () => {
    expect(useThemeSettings.getState().mode).toBe('auto')
  })

  it('setMode updates the theme mode', () => {
    useThemeSettings.getState().setMode('dark')
    expect(useThemeSettings.getState().mode).toBe('dark')
    useThemeSettings.getState().setMode('light')
    expect(useThemeSettings.getState().mode).toBe('light')
  })
})
