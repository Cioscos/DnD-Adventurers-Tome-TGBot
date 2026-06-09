import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InSessionBanner from '@/components/ui/InSessionBanner'

type Session = { id: number; status: string; title?: string; participants: { character_id: number }[] }
const { sessionData, navigateSpy } = vi.hoisted(() => ({
  sessionData: { value: null as Session | null },
  navigateSpy: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => ({ useQuery: () => ({ data: sessionData.value }) }))
vi.mock('react-router-dom', () => ({ useNavigate: () => navigateSpy }))
vi.mock('@/api/client', () => ({ api: { sessions: { me: vi.fn() } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})

afterEach(() => {
  sessionData.value = null
  navigateSpy.mockReset()
})

describe('InSessionBanner', () => {
  it('renders nothing when there is no active session', () => {
    sessionData.value = null
    render(<InSessionBanner charId={7} />)
    expect(screen.queryByLabelText('character.inSession.cta')).not.toBeInTheDocument()
  })

  it('renders nothing when the session is not active', () => {
    sessionData.value = { id: 1, status: 'closed', participants: [{ character_id: 7 }] }
    render(<InSessionBanner charId={7} />)
    expect(screen.queryByLabelText('character.inSession.cta')).not.toBeInTheDocument()
  })

  it('renders nothing when the character is not a participant', () => {
    sessionData.value = { id: 1, status: 'active', participants: [{ character_id: 99 }] }
    render(<InSessionBanner charId={7} />)
    expect(screen.queryByLabelText('character.inSession.cta')).not.toBeInTheDocument()
  })

  it('shows the banner for an active session the character is in, and navigates on tap', async () => {
    sessionData.value = { id: 42, status: 'active', title: 'La Cripta', participants: [{ character_id: 7 }] }
    render(<InSessionBanner charId={7} />)
    expect(screen.getByText('La Cripta')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('character.inSession.cta'))
    expect(navigateSpy).toHaveBeenCalledWith('/session/42')
  })
})
