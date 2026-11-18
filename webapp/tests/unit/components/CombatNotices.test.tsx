import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CombatNotices from '@/components/CombatNotices'

const { state, navigate, toastInfo, setActiveScreen } = vi.hoisted(() => ({
  state: { char: null as unknown, turn: null as unknown },
  navigate: vi.fn(),
  toastInfo: vi.fn(),
  setActiveScreen: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => ({
    data: queryKey[0] === 'character' ? state.char : { status: 'active' },
  }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))
vi.mock('@/hooks/useTurnState', () => ({ useTurnState: () => ({ data: state.turn }) }))
vi.mock('@/store/characterStore', () => ({
  useCharacterStore: (sel: (s: { setActiveScreen: typeof setActiveScreen }) => unknown) => sel({ setActiveScreen }),
}))
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate }))
vi.mock('sonner', () => ({ toast: { info: toastInfo } }))
vi.mock('@/api/client', () => ({ api: {} }))
vi.mock('@/auth/telegram', () => ({ haptic: { light: vi.fn() } }))
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (k: string) => k }) }))

const dyingChar = { current_hit_points: 0, death_saves: { successes: 0, failures: 1, stable: false }, is_dead: false }

beforeEach(() => {
  navigate.mockReset(); toastInfo.mockReset(); setActiveScreen.mockReset()
  state.char = dyingChar
  state.turn = { is_my_turn: true, in_encounter: true, session_id: 5 }
})

describe('CombatNotices', () => {
  it('U41: a 0 PF nel proprio turno invita al TS contro la morte e porta alla scheda', () => {
    render(<CombatNotices charId={7} />)
    fireEvent.click(screen.getByText('character.death_saves.turn_invite'))
    expect(setActiveScreen).toHaveBeenCalledWith(0)
    expect(navigate).toHaveBeenCalledWith('/char/7')
  })

  it('niente invito se stabile o se non è il suo turno', () => {
    state.char = { ...dyingChar, death_saves: { successes: 3, failures: 0, stable: true } }
    const { rerender } = render(<CombatNotices charId={7} />)
    expect(screen.queryByTestId('death-save-invite')).toBeNull()
    state.char = dyingChar
    state.turn = { is_my_turn: false, in_encounter: true, session_id: 5 }
    rerender(<CombatNotices charId={7} />)
    expect(screen.queryByTestId('death-save-invite')).toBeNull()
  })

  it('il banner sparisce dopo il TS contro la morte del turno', () => {
    state.turn = { is_my_turn: true, in_encounter: true, session_id: 5, turn: { death_save_rolled: true } }
    render(<CombatNotices charId={7} />)
    expect(screen.queryByTestId('death-save-invite')).toBeNull()
  })

  it('U30: a fine scontro un toast riporta alla serata', () => {
    state.char = { ...dyingChar, current_hit_points: 10 }
    const { rerender } = render(<CombatNotices charId={7} />)
    expect(toastInfo).not.toHaveBeenCalled()
    state.turn = { is_my_turn: false, in_encounter: false, session_id: 5 }
    rerender(<CombatNotices charId={7} />)
    expect(toastInfo).toHaveBeenCalledTimes(1)
    toastInfo.mock.calls[0][1].action.onClick()
    expect(navigate).toHaveBeenCalledWith('/session/5')
  })

  it('fuori da uno scontro nessun toast', () => {
    state.turn = { is_my_turn: false, in_encounter: false, session_id: 5 }
    render(<CombatNotices charId={7} />)
    expect(toastInfo).not.toHaveBeenCalled()
  })
})
