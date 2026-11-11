import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../../utils/renderWithProviders'
import { useItemCast } from '@/pages/spells/useItemCast'
import { ApiError } from '@/api/client'
import i18n from '@/i18n'
import type { CharacterFull } from '@/types'

const { cast, sessionAllies, toastError } = vi.hoisted(() => ({ cast: vi.fn(), sessionAllies: vi.fn(), toastError: vi.fn() }))
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { items: { cast }, characters: { sessionAllies } } }
})
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...((await orig()) as Record<string, unknown>), useD20Roll: () => async () => undefined }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), info: vi.fn(), error: toastError, warning: vi.fn() } }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children as never) : null) }
})

const item = {
  id: 5, name: 'Bacchetta', item_type: 'generic', quantity: 1, weight: 0, is_equipped: false,
  item_metadata: { granted_spells: [{ name: 'Passo Veloce', srd_index: 'longstrider', level: 1, charges_cost: 1, is_concentration: false }] },
  granted_effects: [{ target_kind: 'allies', max_targets_by_slot: { '1': 1 }, choices: [] }],
}
const char = { id: 7, items: [item], spells: [] } as unknown as CharacterFull

function Harness() {
  const flow = useItemCast(7)
  return (<><button onClick={() => flow.mutate({ itemId: 5, spellIndex: 0, name: 'Passo Veloce' })}>go</button>{flow.elements}</>)
}
function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(['character', 7], char)
  return renderWithProviders(<Harness />, { client })
}

afterEach(() => vi.clearAllMocks())

describe('useItemCast', () => {
  it('asks for the targets of a granted spell the character does not know, using the effect the server sends', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    cast.mockResolvedValue({ ...char, spell_effects: { applied: [{ id: 21, name: 'Eroe' }] } })
    renderIt()
    await userEvent.click(screen.getByText('go'))
    expect(cast).not.toHaveBeenCalled()
    await userEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(cast).toHaveBeenCalledWith(7, 5, 0, { targets: [21], choices: undefined }))
  })

  it('shows the dedicated toast for a target error, never [object Object]', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    cast.mockRejectedValue(new ApiError(409, { code: 'target_dead' }))
    renderIt()
    await userEvent.click(screen.getByText('go'))
    await userEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(i18n.t('character.spells.roll_damage.cast_errors.target_dead')))
  })
})
