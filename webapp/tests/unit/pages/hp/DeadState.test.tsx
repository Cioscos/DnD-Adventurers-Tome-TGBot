import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DeadState from '@/pages/hp/DeadState'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; onConfirm: () => void; onClose: () => void }) =>
      p.open
        ? React.createElement(
            'div',
            { 'data-testid': 'confirm-sheet' },
            React.createElement('button', { 'data-testid': 'cs-confirm', onClick: p.onConfirm }, 'ok'),
            React.createElement('button', { 'data-testid': 'cs-cancel', onClick: p.onClose }, 'cancel'),
          )
        : null,
  }
})

describe('DeadState', () => {
  it('shows the death banner with the death-saves cause', () => {
    render(<DeadState cause="death_saves" onRevive={() => {}} reviving={false} />)
    expect(screen.getByText('character.death_saves.dead_title')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.cause_death_saves')).toBeInTheDocument()
  })

  it('shows the massive-damage cause when killed by massive damage', () => {
    render(<DeadState cause="massive_damage" onRevive={() => {}} reviving={false} />)
    expect(screen.getByText('character.death_saves.cause_massive_damage')).toBeInTheDocument()
  })

  it('revive is gated behind a confirm sheet; confirming calls onRevive once', async () => {
    const onRevive = vi.fn()
    render(<DeadState cause="death_saves" onRevive={onRevive} reviving={false} />)
    // No confirm sheet until the revive button is pressed.
    expect(screen.queryByTestId('confirm-sheet')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'character.death_saves.revive' }))
    expect(screen.getByTestId('confirm-sheet')).toBeInTheDocument()
    await userEvent.click(screen.getByTestId('cs-confirm'))
    expect(onRevive).toHaveBeenCalledTimes(1)
  })

  it('cancelling the confirm sheet does not revive', async () => {
    const onRevive = vi.fn()
    render(<DeadState cause="death_saves" onRevive={onRevive} reviving={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.death_saves.revive' }))
    await userEvent.click(screen.getByTestId('cs-cancel'))
    expect(onRevive).not.toHaveBeenCalled()
    expect(screen.queryByTestId('confirm-sheet')).not.toBeInTheDocument()
  })
})
