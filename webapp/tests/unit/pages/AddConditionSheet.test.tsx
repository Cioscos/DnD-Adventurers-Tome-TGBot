import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import AddConditionSheet from '@/pages/session/AddConditionSheet'
import { api } from '@/api/client'
import type { CombatantLive, EncounterLive } from '@/types'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; title?: string; zClassName?: string; children?: unknown }) => (p.open ? React.createElement('div', { 'data-z': p.zClassName ?? 'z-50', 'data-title': p.title }, React.createElement('h2', null, p.title), p.children) : null) }
})
vi.mock('@/components/ui/SelectSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { options: { value: string; label: string }[]; value: string; onChange: (v: string) => void }) =>
      React.createElement('select', { 'aria-label': 'cond', value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) },
        React.createElement('option', { value: '' }), ...p.options.map((o) => React.createElement('option', { key: o.value, value: o.value }, o.label))),
  }
})
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { sessions: { encounter: { applyCondition: vi.fn().mockResolvedValue({}) } } } }
})

const pc = { id: 5, kind: 'pc', character_id: 9, name: 'Eroe', conditions: {} } as unknown as CombatantLive

describe('AddConditionSheet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('asks for confirmation before the GM sets a PC to exhaustion 6, and sends only on confirm', async () => {
    renderWithProviders(
      <AddConditionSheet sessionId={1} encounter={{ combatants: [pc] } as unknown as EncounterLive} target={pc} liveCharacters={[]} onClose={() => {}} />,
    )
    fireEvent.change(screen.getByLabelText('cond'), { target: { value: 'exhaustion' } })
    for (let i = 0; i < 5; i++) await userEvent.click(screen.getByLabelText('+'))
    await userEvent.click(screen.getByText('Applica condizione'))
    expect(api.sessions.encounter.applyCondition).not.toHaveBeenCalled()
    await userEvent.click(screen.getByText('Conferma la morte'))
    expect(api.sessions.encounter.applyCondition).toHaveBeenCalledWith(1, 5, { slug: 'exhaustion', value: 6 })
  })

  it('opens the lethal confirmation above the condition sheet (z-index), not behind it', async () => {
    const { container } = renderWithProviders(
      <AddConditionSheet sessionId={1} encounter={{ combatants: [pc] } as unknown as EncounterLive} target={pc} liveCharacters={[]} onClose={() => {}} />,
    )
    fireEvent.change(screen.getByLabelText('cond'), { target: { value: 'exhaustion' } })
    for (let i = 0; i < 5; i++) await userEvent.click(screen.getByLabelText('+'))
    await userEvent.click(screen.getByText('Applica condizione'))
    const z = (el: Element | null) => Number(/z-\[(\d+)\]/.exec(el?.getAttribute('data-z') ?? '')?.[1] ?? 50)
    const sheets = [...container.querySelectorAll('[data-z]')]
    const confirm = sheets.find((e) => e.contains(screen.getByText('Conferma la morte')) && !e.querySelector('[data-z]'))
    const parent = sheets.find((e) => e !== confirm && e.contains(confirm!))
    expect(z(confirm ?? null)).toBeGreaterThan(z(parent ?? null))
  })
})
