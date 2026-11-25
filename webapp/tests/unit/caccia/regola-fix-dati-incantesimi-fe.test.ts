import { createElement, Fragment } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
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
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string, o?: { level?: number }) => (o?.level ? `${k} ${o.level}` : k), i18n: { language: 'it' } }),
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig<Record<string, unknown>>()), useD20Roll: () => async () => 10 }))

// Produrre Fiamma 2024 come lo aggiunge il catalogo (spells-2024.json): azione bonus, attacco a distanza 1d8 fuoco
const produrreFiamma = {
  id: 21, name: 'Produrre Fiamma', level: 0, srd_index: 'produce-flame', attack_save: 'ATK', casting_time: '1 azione bonus',
  is_concentration: false, is_ritual: false, damage_dice: '1d8', damage_type: 'fire', is_prepared: true,
  effect: { target_kind: 'self', max_targets_by_slot: {}, choices: [], lit: false },
} as unknown as Spell

const druido = {
  id: 7, rules_edition: '2024', spells: [produrreFiamma], spell_slots: [], settings: {},
  spellcasting: { has_preparing_class: false, has_wizard: false, has_ritual_caster: false, casters: [] },
} as unknown as CharacterFull

function Banco({ spell = produrreFiamma, pg = druido }: { spell?: Spell; pg?: CharacterFull }) {
  const flow = useCastFlow(7, pg)
  return createElement(Fragment, null,
    createElement('button', { onClick: () => flow.beginCast(spell) }, 'lancia'),
    flow.canRollActiveDamage(spell) ? 'danni senza attacco' : null,
    flow.elements)
}

afterEach(() => { vi.clearAllMocks() })

describe('caccia: correzioni del gruppo dati-incantesimi-fe', () => {
  // caccia: {"id": "CB-4037", "fonte": "2024 · Incantesimi · Produrre Fiamma (il lancio crea la fiamma, scagliarla è un'azione Magia) · pag. 308", "zona": "regola:2024/incantesimi-M-R", "voce": "regola", "copre": ["carta:2024/spells.md#Produrre Fiamma", "route:/char/:id/spells"]}
  it('Produrre Fiamma 2024 al lancio crea la fiamma senza scagliarla', async () => {
    vi.mocked(api.spells.use).mockResolvedValue({} as never)
    vi.mocked(api.spells.attack).mockResolvedValue({} as never)
    renderWithProviders(createElement(Banco), { client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
    await userEvent.click(screen.getByText('lancia'))
    // il lancio (azione bonus) dà la fiamma per 10 minuti; ogni lancio della fiamma è un attacco a parte che costa l'azione
    await waitFor(() => expect(api.spells.use).toHaveBeenCalled())
    expect(api.spells.attack).not.toHaveBeenCalled()
  })

  // caccia: {"id": "CB-4646", "fonte": "2024 · Incantesimi · Produrre Fiamma (finché dura la fiamma si scaglia con un'azione, senza un altro lancio) · pag. 308", "zona": "regola:2024/incantesimi-M-R", "voce": "regola", "copre": ["carta:2024/spells.md#Produrre Fiamma", "route:/char/:id/spells"]}
  it('Produrre Fiamma 2024 accesa si scaglia senza lanciarla di nuovo', async () => {
    vi.mocked(api.spells.attack).mockResolvedValue({} as never)
    const accesa = { ...produrreFiamma, effective_casting_time: '1 azione', effect: { ...produrreFiamma.effect!, lit: true } }
    renderWithProviders(createElement(Banco, { spell: accesa }), { client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
    await userEvent.click(screen.getByText('lancia'))
    await waitFor(() => expect(api.spells.attack).toHaveBeenCalled())
    expect(api.spells.use).not.toHaveBeenCalled()
  })

  // caccia: {"id": "CB-4876", "fonte": "decisione D-047 (tests/caccia/decisioni.md): il lancio crea la lama, ogni attacco è un'azione con il suo tiro e i danni dello slot del lancio; 2014 · Lama Infuocata · pag. 247; 2024 · pag. 275", "zona": "regola:2014/incantesimi-G-L", "voce": "interazione", "copre": ["carta:2014/spells.md#Lama Infuocata", "carta:2024/spells.md#Lama infuocata", "route:/char/:id/spells"]}
  it('Lama Infuocata si lancia con lo slot senza attaccare, poi attacca senza slot con i danni dello slot del lancio', async () => {
    vi.mocked(api.spells.use).mockResolvedValue({} as never)
    vi.mocked(api.spells.attack).mockResolvedValue({ spell_name: 'Lama Infuocata', to_hit_die: 12, to_hit_bonus: 5, to_hit_total: 17, is_critical: false, is_fumble: false, character: {} } as never)
    const lama = { ...produrreFiamma, id: 22, name: 'Lama Infuocata', level: 2, srd_index: 'flame-blade', is_concentration: true, damage_dice: '3d6' }
    const pg = { ...druido, spells: [lama], spell_slots: [{ id: 4, level: 4, total: 1, used: 0, available: 1, is_pact: false }] } as unknown as CharacterFull
    const client = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const { unmount } = renderWithProviders(createElement(Banco, { spell: lama, pg }), { client: client() })
    await userEvent.click(screen.getByText('lancia'))
    fireEvent.click(await screen.findByText('character.slots.level 4'))
    await waitFor(() => expect(api.spells.use).toHaveBeenCalledWith(7, 22, expect.objectContaining({ slot_id: 4, slot_level: 4 })))
    expect(api.spells.attack).not.toHaveBeenCalled()
    unmount()
    vi.clearAllMocks()
    const accesa = { ...lama, effective_casting_time: '1 azione', effect: { ...lama.effect!, lit: true } }
    renderWithProviders(createElement(Banco, { spell: accesa, pg: { ...pg, concentrating_spell_id: 22, settings: { concentration_level: 4 } } as CharacterFull }), { client: client() })
    expect(screen.queryByText('danni senza attacco')).toBeNull()
    await userEvent.click(screen.getByText('lancia'))
    await waitFor(() => expect(api.spells.attack).toHaveBeenCalledWith(7, 22, expect.objectContaining({ slot_id: undefined, slot_level: null })))
    expect(api.spells.castCheck).not.toHaveBeenCalled()  // non è un lancio
    expect(api.spells.use).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByText('character.spells.attack_roll_damage'))
    expect(await screen.findByText('character.spells.roll_damage.roll_button')).toBeInTheDocument()
    expect(screen.getByText('character.slots.level 4')).toBeInTheDocument()
  })
})
