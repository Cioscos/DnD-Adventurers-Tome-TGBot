import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import WildMagicSheet from '@/components/rules/WildMagicSheet'
import type { CharacterFull } from '@/types'

const { wildMagicSurge, wildMagicChoose, wildMagicTable, toastError } = vi.hoisted(() => ({ wildMagicSurge: vi.fn(), wildMagicChoose: vi.fn(), wildMagicTable: vi.fn(), toastError: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { wildMagicSurge, wildMagicChoose, wildMagicTable } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: toastError, success: vi.fn() }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})

const entry = (lo: number, name: string) => ({ roll: lo, lo, hi: lo + 1, label: `${lo}`, name: { it: name, en: name }, text: { it: `testo ${name}`, en: `text ${name}` } })
const applied = (lo: number, name: string, extra: Record<string, unknown> = {}) => ({
  ...entry(lo, name), healed: 0, slot_level: null, points: false, extra_action: false, dc: null, state: null, damage: null, extra_roll: null, ...extra,
})
const char = (tidesUses?: number, repeating = false) => ({
  id: 7,
  abilities: tidesUses === undefined ? [] : [{ id: 1, feature_key: 'sorcerer.tides_of_chaos', max_uses: 1, uses: tidesUses }],
  active_states: repeating ? [{ key: 'wild_repeat', rounds_left: 10 }] : [],
}) as unknown as CharacterFull

describe('WildMagicSheet', () => {
  it('rolls only after the player confirms that the GM asked for the surge', async () => {
    wildMagicSurge.mockResolvedValue({ die: 7, triggered: false, pending: false, options: [], applied: null, tides_restored: false })
    renderWithProviders(<WildMagicSheet char={char()} onClose={() => {}} />)
    const go = screen.getByText('character.turn.wild.roll').closest('button') as HTMLButtonElement
    expect(go).toBeDisabled()
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(go)
    await waitFor(() => expect(wildMagicSurge).toHaveBeenCalledWith(7, { tides: false }))
    expect(await screen.findByText(/character.turn.wild.no_surge/)).toBeInTheDocument()
  })

  it('shows what the surge did: the result, the hit points and the timer', async () => {
    wildMagicSurge.mockResolvedValue({
      die: 1, triggered: true, pending: false, options: [entry(39, 'Cura')], applied: applied(39, 'Cura', { healed: 9, state: { key: 'x', rounds_left: 10 } }), tides_restored: false,
    })
    renderWithProviders(<WildMagicSheet char={char()} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByText('character.turn.wild.roll'))
    expect((await screen.findAllByText(/Cura/)).length).toBeGreaterThan(0)
    expect(screen.getByText(/character.turn.wild.healed.*9/)).toBeInTheDocument()
    expect(screen.getByText(/character.turn.wild.timer.*10/)).toBeInTheDocument()
  })

  it('lets the player choose between the two results of Controlled Chaos and applies only the chosen one', async () => {
    wildMagicSurge.mockResolvedValue({ die: 1, triggered: true, pending: true, options: [entry(7, 'Palla'), entry(19, 'Unto')], applied: null, tides_restored: false })
    wildMagicChoose.mockResolvedValue({ die: null, triggered: true, pending: false, options: [], applied: applied(19, 'Unto'), tides_restored: false })
    renderWithProviders(<WildMagicSheet char={char()} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByText('character.turn.wild.roll'))
    const buttons = await screen.findAllByText('character.turn.wild.choose')
    expect(buttons).toHaveLength(2)
    await userEvent.click(buttons[1])
    await waitFor(() => expect(wildMagicChoose).toHaveBeenCalledWith(7, 1))
  })

  it('offers the table without the d20 only when Tides of Chaos has been spent', async () => {
    wildMagicSurge.mockResolvedValue({ die: null, triggered: true, pending: false, options: [entry(17, 'Piume')], applied: applied(17, 'Piume'), tides_restored: true })
    const { unmount } = renderWithProviders(<WildMagicSheet char={char(1)} onClose={() => {}} />)
    expect(screen.queryByText('character.turn.wild.tides')).not.toBeInTheDocument()
    unmount()
    renderWithProviders(<WildMagicSheet char={char(0)} onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.turn.wild.tides'))
    await waitFor(() => expect(wildMagicSurge).toHaveBeenCalledWith(7, { tides: true }))
    expect(await screen.findByText('character.turn.wild.tides_back')).toBeInTheDocument()
  })

  it('says why the server refused, never the technical message', async () => {
    const { ApiError } = await import('@/api/client')
    wildMagicSurge.mockRejectedValue(new ApiError(409, { code: 'once_per_turn' }))
    renderWithProviders(<WildMagicSheet char={char()} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByText('character.turn.wild.roll'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.turn.wild.errors.once_per_turn'))
  })

  it('offers the table at each turn only while the repeat surge lasts, and says when a new repeat is ignored', async () => {
    wildMagicSurge.mockResolvedValue({ die: null, triggered: true, pending: false, options: [entry(1, 'Ripetizione')], applied: applied(1, 'Ripetizione', { ignored: true }), tides_restored: false })
    const { unmount } = renderWithProviders(<WildMagicSheet char={char()} onClose={() => {}} />)
    expect(screen.queryByText('character.turn.wild.repeat')).not.toBeInTheDocument()
    unmount()
    renderWithProviders(<WildMagicSheet char={char(undefined, true)} onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.turn.wild.repeat'))
    await waitFor(() => expect(wildMagicSurge).toHaveBeenCalledWith(7, { repeat: true }))
    expect(await screen.findByText('character.turn.wild.ignored')).toBeInTheDocument()
  })

  describe('2024', () => {
    const char24 = (extra: Record<string, unknown> = {}) => ({
      id: 7, rules_edition: '2024', abilities: [{ id: 1, feature_key: 'sorcerer.tides_of_chaos', max_uses: 1, uses: 1 }], active_states: [], ...extra,
    }) as unknown as CharacterFull

    it('lets the player roll the d20 right away, with the 2024 text and without the 2014 GM switch', async () => {
      wildMagicSurge.mockResolvedValue({ die: 7, triggered: false, pending: false, options: [], applied: null, tides_restored: false })
      renderWithProviders(<WildMagicSheet char={char24()} onClose={() => {}} />)
      expect(screen.getByText('character.turn.wild.intro_2024')).toBeInTheDocument()
      expect(screen.queryByText('character.turn.wild.intro')).not.toBeInTheDocument()
      expect(screen.queryByRole('switch')).not.toBeInTheDocument()
      await userEvent.click(screen.getByText('character.turn.wild.roll'))
      await waitFor(() => expect(wildMagicSurge).toHaveBeenCalledWith(7, { tides: false }))
    })

    it('offers the table after the Tides only once a slot spell has been cast (the due state), never from the spent use alone', async () => {
      wildMagicSurge.mockResolvedValue({ die: null, triggered: true, pending: false, options: [entry(17, 'Piume')], applied: applied(17, 'Piume'), tides_restored: true })
      const spent = [{ id: 1, feature_key: 'sorcerer.tides_of_chaos', max_uses: 1, uses: 0 }]
      const { unmount } = renderWithProviders(<WildMagicSheet char={char24({ abilities: spent })} onClose={() => {}} />)
      expect(screen.queryByText('character.turn.wild.tides_2024')).not.toBeInTheDocument()
      unmount()
      renderWithProviders(<WildMagicSheet char={char24({ abilities: spent, active_states: [{ key: 'tides_surge_due', rounds_left: null }] })} onClose={() => {}} />)
      await userEvent.click(screen.getByText('character.turn.wild.tides_2024'))
      await waitFor(() => expect(wildMagicSurge).toHaveBeenCalledWith(7, { tides: true }))
    })

    it('picks a Tamed Surge effect by name, never the last row, and sends only that percentile', async () => {
      wildMagicTable.mockResolvedValue([entry(1, 'Ripetizione'), entry(53, 'Azione extra'), entry(97, 'Ultima')])
      wildMagicSurge.mockResolvedValue({ die: null, triggered: true, pending: false, options: [entry(53, 'Azione extra')], applied: applied(53, 'Azione extra', { extra_action: true }), tides_restored: false })
      const tamed = [{ id: 2, feature_key: 'sorcerer.tamed_surge', max_uses: 1, uses: 1 }]
      renderWithProviders(<WildMagicSheet char={char24({ abilities: tamed })} onClose={() => {}} />)
      expect(await screen.findByText('53 · Azione extra')).toBeInTheDocument()
      expect(screen.queryByText(/Ultima/)).not.toBeInTheDocument()
      await userEvent.click(screen.getByText('53 · Azione extra'))
      await userEvent.click(screen.getByText('character.turn.wild.tamed_apply'))
      await waitFor(() => expect(wildMagicSurge).toHaveBeenCalledWith(7, { tamed: true, percentile: [53] }))
    })

    it('hides Tamed Surge when its use is spent', async () => {
      wildMagicTable.mockResolvedValue([entry(1, 'Ripetizione')])
      const spent = [{ id: 2, feature_key: 'sorcerer.tamed_surge', max_uses: 1, uses: 0 }]
      renderWithProviders(<WildMagicSheet char={char24({ abilities: spent })} onClose={() => {}} />)
      expect(screen.queryByText('character.turn.wild.tamed_apply')).not.toBeInTheDocument()
    })
  })
})
