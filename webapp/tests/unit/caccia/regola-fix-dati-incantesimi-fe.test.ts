import { createElement, Fragment } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import { api } from '@/api/client'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import type { CharacterFull, Spell } from '@/types'

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  api: { spells: { attack: vi.fn(), use: vi.fn(), updateConcentration: vi.fn(), castCheck: vi.fn() }, characters: { sessionAllies: vi.fn(), turnState: vi.fn() } },
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() } }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig<Record<string, unknown>>()), useD20Roll: () => async () => 10 }))

// Produrre Fiamma 2024 come lo aggiunge il catalogo (spells-2024.json): azione bonus, attacco a distanza 1d8 fuoco
const produrreFiamma = {
  id: 21, name: 'Produrre Fiamma', level: 0, srd_index: 'produce-flame', attack_save: 'ATK', casting_time: '1 azione bonus',
  is_concentration: false, is_ritual: false, damage_dice: '1d8', damage_type: 'fire', is_prepared: true,
} as unknown as Spell

const druido = {
  id: 7, rules_edition: '2024', spells: [produrreFiamma], spell_slots: [], settings: {},
  spellcasting: { has_preparing_class: false, has_wizard: false, has_ritual_caster: false, casters: [] },
} as unknown as CharacterFull

function Banco() {
  const flow = useCastFlow(7, druido)
  return createElement(Fragment, null,
    createElement('button', { onClick: () => flow.beginCast(produrreFiamma) }, 'lancia'),
    flow.elements)
}

afterEach(() => { vi.clearAllMocks() })

describe('caccia: correzioni del gruppo dati-incantesimi-fe', () => {
  // caccia: {"id": "CB-4037", "fonte": "2024 · Incantesimi · Produrre Fiamma (il lancio crea la fiamma, scagliarla è un'azione Magia) · pag. 308", "zona": "regola:2024/incantesimi-M-R", "voce": "regola", "copre": ["carta:2024/spells.md#Produrre Fiamma", "route:/char/:id/spells"]}
  it.fails('Produrre Fiamma 2024 al lancio crea la fiamma senza scagliarla', async () => {
    vi.mocked(api.spells.use).mockResolvedValue({} as never)
    vi.mocked(api.spells.attack).mockResolvedValue({} as never)
    renderWithProviders(createElement(Banco), { client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
    await userEvent.click(screen.getByText('lancia'))
    // il lancio (azione bonus) dà la fiamma per 10 minuti; ogni lancio della fiamma è un attacco a parte che costa l'azione
    await waitFor(() => expect(api.spells.use).toHaveBeenCalled())
    expect(api.spells.attack).not.toHaveBeenCalled()
  })
})
