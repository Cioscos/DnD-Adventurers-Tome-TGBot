import { describe, it, expect } from 'vitest'
import { currentVersion, changelog, localizedLines, localizedTitle } from '@/lib/version'

describe('version', () => {
  it('currentVersion is the newest changelog entry version (SemVer)', () => {
    expect(currentVersion()).toBe(changelog[0].version)
    expect(currentVersion()).toMatch(/^\d+\.\d+\.\d+/)
  })

  it('localizedLines picks the locale list and falls back to it when en is empty', () => {
    expect(localizedLines({ it: ['a'], en: ['b'] }, 'it')).toEqual(['a'])
    expect(localizedLines({ it: ['a'], en: ['b'] }, 'en')).toEqual(['b'])
    expect(localizedLines({ it: ['a'], en: [] }, 'en')).toEqual(['a'])
    expect(localizedLines(undefined, 'it')).toEqual([])
  })

  it('localizedTitle picks the locale title with an it fallback', () => {
    const entry = { version: '1.0.0', date: '2026-01-01', title: { it: 'Titolo', en: 'Title' } }
    expect(localizedTitle(entry, 'it')).toBe('Titolo')
    expect(localizedTitle(entry, 'en')).toBe('Title')
    expect(localizedTitle({ version: '1.0.0', date: '2026-01-01' }, 'it')).toBeUndefined()
  })
})
