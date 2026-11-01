import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import CombatEntryCard from '@/components/session/CombatEntryCard'
import type { CombatantLive, EncounterLive, GameSessionLive } from '@/types'

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k) }),
}))
vi.mock('@/pages/session/EncounterCreateSheet', () => ({
  default: ({ onCreated }: { onCreated?: () => void }) => (
    <button data-testid="create-sheet" onClick={onCreated}>create</button>
  ),
}))

const goblin: CombatantLive = {
  id: 5, kind: 'monster', name: 'Goblin', initiative: 17, initiative_die: null, initiative_mod: 0,
  sort_order: 1, is_dead: false, conditions: {}, current_hp: null, max_hp: null, ac: null, hp_bucket: null,
}
const enc = (over: Partial<EncounterLive>): EncounterLive => ({
  id: 1, mode: 'full', status: 'active', round: 3, active_combatant_id: 5,
  created_at: '', started_at: null, ended_at: null, combatants: [goblin], ...over,
})
const live = (e: EncounterLive | null): GameSessionLive => ({
  id: 12, code: 'ABC123', gm_user_id: 1, gm_display_name: 'GM', status: 'active', title: null,
  created_at: '', closed_at: null, participants: [], live_characters: [], encounter: e,
})

beforeEach(() => navigateSpy.mockReset())

describe('CombatEntryCard', () => {
  it('active: shows round and who acts, tap opens the combat page', () => {
    render(<CombatEntryCard live={live(enc({}))} sessionId={12} amGm={false} />)
    const card = screen.getByTestId('combat-entry-card')
    expect(card).toHaveTextContent('session.combat.entry_active')
    expect(card).toHaveTextContent('"n":3')
    expect(card).toHaveTextContent('"name":"Goblin"')
    fireEvent.click(within(card).getByRole('button'))
    expect(navigateSpy).toHaveBeenCalledWith('/session/12/combat')
  })

  it('setup, player: tells them to roll initiative', () => {
    render(<CombatEntryCard live={live(enc({ status: 'setup', active_combatant_id: null }))} sessionId={12} amGm={false} />)
    const card = screen.getByTestId('combat-entry-card')
    expect(card).toHaveTextContent('session.combat.entry_setup')
    expect(card).toHaveTextContent('session.combat.entry_setup_player')
  })

  it('no encounter, GM: start button, then goes to the combat page once created', () => {
    render(<CombatEntryCard live={live(null)} sessionId={12} amGm />)
    fireEvent.click(screen.getByText('session.combat.start_encounter'))
    fireEvent.click(screen.getByTestId('create-sheet'))
    expect(navigateSpy).toHaveBeenCalledWith('/session/12/combat')
  })

  it('no encounter, player: renders nothing', () => {
    const { container } = render(<CombatEntryCard live={live(null)} sessionId={12} amGm={false} />)
    expect(container).toBeEmptyDOMElement()
  })
})
