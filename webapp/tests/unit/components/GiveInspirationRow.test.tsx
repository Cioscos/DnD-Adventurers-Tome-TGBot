import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import GiveInspirationRow from '@/components/character/GiveInspirationRow'

const { giveInspiration, updateInspiration, discardExtra, partners } = vi.hoisted(() => ({
  updateInspiration: vi.fn(),
  discardExtra: vi.fn().mockResolvedValue({ id: 7, heroic_inspiration: true, inspiration_extra: false }),
  giveInspiration: vi.fn().mockResolvedValue({ id: 7, heroic_inspiration: false }),
  partners: { current: null as null | { sessionId: number; partners: { user_id: number }[]; stash: boolean } },
}))
vi.mock('@/api/client', () => ({
  api: { sessions: { giveInspiration }, characters: { updateInspiration, discardExtraInspiration: discardExtra } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('@/hooks/useTradePartners', () => ({ useTradePartners: () => partners.current }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: vi.fn(), light: vi.fn() } }))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})
vi.mock('@/pages/inventory/GiveSheet', async () => {
  const React = await import('react')
  return {
    PartnerPicker: (p: { onChange: (id: number) => void }) =>
      React.createElement('button', { onClick: () => p.onChange(55) }, 'pick'),
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; children?: ReactNode }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children) }
})

const char = { id: 7, rules_edition: '2024', heroic_inspiration: true } as never

beforeEach(() => {
  giveInspiration.mockClear()
  updateInspiration.mockReset()
  partners.current = { sessionId: 3, partners: [{ user_id: 55 }, { user_id: 66 }], stash: false }
})

describe('GiveInspirationRow', () => {
  it('asks to give only after the server says an extra Inspiration arrived, and keeps yours', async () => {
    updateInspiration.mockResolvedValue({ ...(char as object), inspiration_extra: true })
    renderWithProviders(<GiveInspirationRow char={char} />)
    expect(screen.queryByText('character.inspiration.give_confirm')).toBeNull()  // nessuna cessione senza un'altra ricevuta
    await userEvent.click(screen.getByText('character.inspiration.received_another'))
    await waitFor(() => expect(updateInspiration).toHaveBeenCalledWith(7, true))
    expect(await screen.findByText('character.inspiration.give_confirm')).toBeInTheDocument()
    await userEvent.click(screen.getByText('pick'))
    await userEvent.click(screen.getByText('character.inspiration.give_confirm'))
    await waitFor(() => expect(giveInspiration).toHaveBeenCalledWith(3, { from_character_id: 7, to_user_id: 55 }))
  })

  it('offers the pending extra again when the sheet was closed', async () => {
    renderWithProviders(<GiveInspirationRow char={{ ...(char as object), inspiration_extra: true } as never} />)
    await userEvent.click(screen.getByText('character.inspiration.give'))
    expect(screen.getByText('character.inspiration.give_confirm')).toBeInTheDocument()
    expect(updateInspiration).not.toHaveBeenCalled()
  })

  it.each([
    ['without Inspiration', { heroic_inspiration: false }, true],
    ['outside a session', {}, false],
  ])('shows nothing %s', (_name, over, inSession) => {
    if (!inSession) partners.current = null
    const { container } = renderWithProviders(<GiveInspirationRow char={{ ...(char as object), ...over } as never} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lets the player discard the extra one he does not want to give, keeping his own', async () => {
    const { container } = renderWithProviders(<GiveInspirationRow char={{ ...(char as object), inspiration_extra: true } as never} />)
    await userEvent.click(screen.getByText('character.inspiration.discard'))
    await waitFor(() => expect(discardExtra).toHaveBeenCalledWith(7))
    expect(container).not.toBeEmptyDOMElement()
  })

  it('offers no discard until an extra one arrived', () => {
    renderWithProviders(<GiveInspirationRow char={char} />)
    expect(screen.queryByText('character.inspiration.discard')).toBeNull()
  })

  it('in 2014 gives your own Inspiration straight away, with no "received another" step', async () => {
    renderWithProviders(<GiveInspirationRow char={{ ...(char as object), rules_edition: '2014' } as never} />)
    expect(screen.queryByText('character.inspiration.received_another')).toBeNull()
    await userEvent.click(screen.getByText('character.inspiration.give_own'))
    await userEvent.click(screen.getByText('pick'))
    await userEvent.click(screen.getByText('character.inspiration.give_confirm'))
    await waitFor(() => expect(giveInspiration).toHaveBeenCalledWith(3, { from_character_id: 7, to_user_id: 55 }))
    expect(updateInspiration).not.toHaveBeenCalled()
  })
})
