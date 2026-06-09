import { describe, it, expect, beforeEach, vi } from 'vitest'

// getLanguageCode is read once at module init to seed `locale`. A hoisted,
// mutable holder lets the derivation test re-evaluate it after resetModules.
const mockLang = vi.hoisted(() => ({ code: 'it-IT' }))
vi.mock('@/auth/telegram', () => ({ getLanguageCode: () => mockLang.code }))

import { useCharacterStore } from '@/store/characterStore'

describe('useCharacterStore', () => {
  beforeEach(() => {
    useCharacterStore.setState({ activeCharId: null, activeScreen: 0, locale: 'it' })
  })

  it('derives locale "it" from an Italian Telegram language code', () => {
    expect(useCharacterStore.getState().locale).toBe('it')
  })

  it('setActiveCharId resets the active screen to 0 when the id changes', () => {
    const { setActiveCharId, setActiveScreen } = useCharacterStore.getState()
    setActiveCharId(5)
    setActiveScreen(2)
    expect(useCharacterStore.getState().activeScreen).toBe(2)

    setActiveCharId(9) // different id → screen resets
    expect(useCharacterStore.getState().activeCharId).toBe(9)
    expect(useCharacterStore.getState().activeScreen).toBe(0)
  })

  it('setActiveCharId keeps the active screen when the id is unchanged', () => {
    const { setActiveCharId, setActiveScreen } = useCharacterStore.getState()
    setActiveCharId(5)
    setActiveScreen(2)
    setActiveCharId(5) // same id → screen preserved
    expect(useCharacterStore.getState().activeScreen).toBe(2)
  })

  it('setActiveScreen updates the screen index', () => {
    useCharacterStore.getState().setActiveScreen(1)
    expect(useCharacterStore.getState().activeScreen).toBe(1)
  })

  it('setLocale overrides the language', () => {
    useCharacterStore.getState().setLocale('en')
    expect(useCharacterStore.getState().locale).toBe('en')
  })
})

describe('useCharacterStore locale derivation', () => {
  it('falls back to "en" for a non-Italian language code', async () => {
    mockLang.code = 'en-US'
    vi.resetModules()
    const { useCharacterStore: freshStore } = await import('@/store/characterStore')
    expect(freshStore.getState().locale).toBe('en')
    mockLang.code = 'it-IT' // restore for any later imports
  })
})
