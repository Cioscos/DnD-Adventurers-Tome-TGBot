import { createElement, Fragment } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
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
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig<Record<string, unknown>>()), useD20Roll: () => async () => undefined }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/pages/spells/SpellDamageSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { spell: Spell | null; slotLevel: number | null }) =>
      p.spell ? React.createElement('div', { 'data-testid': 'damage-sheet', 'data-slot': String(p.slotLevel) }) : null,
  }
})

// Dardo Stregato 2014 come lo aggiunge il catalogo (spells.json): 1d12 fulmine, +1d12 per slot oltre il 1°
const dardoStregato = {
  id: 11, name: 'Dardo Stregato', level: 1, srd_index: 'witch-bolt', attack_save: 'ATK', is_concentration: true, is_ritual: false,
  damage_dice: '1d12', damage_type: 'lightning', higher_levels_dice: '1d12', is_prepared: true,
} as unknown as Spell

// Lanciato con uno slot di 3° livello: la concentrazione ricorda il livello del lancio
const stregone = {
  id: 7, rules_edition: '2014', spells: [dardoStregato], spell_slots: [], concentrating_spell_id: 11,
  settings: { concentration_level: 3 },
  spellcasting: { has_preparing_class: false, has_wizard: false, has_ritual_caster: false, casters: [] },
} as unknown as CharacterFull

function Banco() {
  const flow = useCastFlow(7, stregone)
  return createElement(Fragment, null,
    flow.canRollActiveDamage(dardoStregato)
      ? createElement('button', { onClick: () => flow.rollActiveDamage(dardoStregato) }, 'danni-turno-dopo')
      : null,
    flow.elements)
}

afterEach(() => { vi.clearAllMocks() })

describe('caccia: regola 2014 incantesimi D-F', () => {
  // caccia: {"id": "CB-3264", "fonte": "2014 · Incantesimi · Dardo Stregato (solo il danno iniziale cresce con lo slot) · pag. 228", "zona": "regola:2014/incantesimi-D-F", "voce": "regola", "copre": ["carta:2014/spells.md#Dardo Stregato", "route:/char/:id/spells"]}
  it('il danno dei turni dopo di Dardo Stregato resta 1d12 anche lanciato con uno slot più alto', async () => {
    renderWithProviders(createElement(Banco), { client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
    await userEvent.click(screen.getByText('danni-turno-dopo'))
    // solo il danno iniziale cresce con lo slot: il tiro del turno dopo si fa al livello dell'incantesimo
    expect((await screen.findByTestId('damage-sheet')).dataset.slot).toBe('1')
  })
})
