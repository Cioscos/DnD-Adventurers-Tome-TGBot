import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../utils/renderWithProviders'
import CampaignRecap from '@/pages/CampaignRecap'
import { ApiError } from '@/api/client'

const { recap, campaignGet, shareRecap, shareTelegramMessage } = vi.hoisted(() => ({
  recap: vi.fn(), campaignGet: vi.fn(), shareRecap: vi.fn(), shareTelegramMessage: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { sessions: { recap }, campaigns: { get: campaignGet }, share: { recap: shareRecap } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: vi.fn(), success: vi.fn() }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k),
      i18n: { language: 'it' },
    }),
  }
})
vi.mock('@/auth/telegram', () => ({
  haptic: new Proxy({}, { get: () => () => {} }),
  canShareMessage: () => true,
  shareTelegramMessage,
}))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

const RECAP = {
  version: 1, session_id: 8, campaign_id: 5, campaign_name: 'La Coda del Vento', number: 3,
  started_at: '2026-10-28T20:00:00', ended_at: '2026-10-28T23:40:00', duration_seconds: 13200,
  characters: [{
    character_id: 10, name: 'Thorin', player_name: 'Aldo', class_summary: 'Guerriero 5', level: 5,
    dice: { rolls: 31, nat20: 2, nat1: 1, highest: 27 }, damage_taken: 44, healed: 12, downed: 1,
    death_saves: { successes: 2, failures: 1 }, spells_cast: 3, slots_used: { '1': 2, '3': 1 },
    rests: { short: 1, long: 0 }, conditions: ['poisoned', 'custom:Sanguinamento'],
  }],
  combat: { encounters: 2, rounds: 9, monsters: ['Goblin', 'Orco'] },
  items: {
    gm_grants: [{ to: 'Thorin', item: 'Spada lunga', quantity: 1 }],
    trades: [{ from: 'Thorin', to: 'Grom', summary: 'Pozione ×2' }],
    stash: [{ kind: 'stash_put', who: 'Grom', summary: '15 mo' }],
  },
  lore: [{ id: 1, title: 'Il tempio sommerso' }],
  highlights: [{ key: 'luckiest', character_id: 10, name: 'Thorin', value: 2 }],
}

const renderPage = () => renderWithProviders(
  <Routes><Route path="/campaign/:id/recap/:sessionId" element={<CampaignRecap />} /></Routes>,
  { route: '/campaign/5/recap/8' },
)
afterEach(() => { vi.clearAllMocks() })

describe('CampaignRecap', () => {
  it('shows exhaustion with its level, or the plain name on old recaps', async () => {
    const c = RECAP.characters[0]
    recap.mockResolvedValue({ ...RECAP, characters: [{ ...c, conditions: ['exhaustion'], condition_levels: { exhaustion: 3 } }] })
    campaignGet.mockResolvedValue({ id: 5, is_gm: false })
    const { unmount } = renderPage()
    expect(await screen.findByText(/character\.conditions\.exhaustion:\{"level":3/)).toBeInTheDocument()
    unmount()
    recap.mockResolvedValue({ ...RECAP, characters: [{ ...c, conditions: ['exhaustion'] }] })
    renderPage()
    expect(await screen.findByText('campaign.recap.exhaustion')).toBeInTheDocument()
  })

  it('renders header, PC card, combat, items, lore and highlights', async () => {
    recap.mockResolvedValue(RECAP)
    campaignGet.mockResolvedValue({ id: 5, is_gm: false })
    renderPage()
    expect(await screen.findByText(/campaign\.recap\.evening:\{"n":3\}/)).toBeInTheDocument()
    expect(screen.getByText('3h 40m')).toBeInTheDocument()
    expect(screen.getByText('Thorin', { selector: 'h3' })).toBeInTheDocument()
    expect(screen.getByText('44')).toBeInTheDocument()
    expect(screen.getByText(/character.conditions.poisoned/)).toBeInTheDocument()
    expect(screen.getByText('Sanguinamento')).toBeInTheDocument()
    expect(screen.getByText('campaign.recap.ds_s:{"count":2} · campaign.recap.ds_f:{"count":1}')).toBeInTheDocument()
    expect(screen.getByText(/Goblin, Orco/)).toBeInTheDocument()
    expect(screen.getByText(/Spada lunga/)).toBeInTheDocument()
    expect(screen.getByText(/Pozione ×2/)).toBeInTheDocument()
    expect(screen.getByText('Il tempio sommerso')).toBeInTheDocument()
    expect(screen.getByText(/campaign\.recap\.hl_luckiest/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'campaign.recap.share' })).toBeNull()
  })

  it('hides empty sections', async () => {
    recap.mockResolvedValue({
      ...RECAP, characters: [], combat: { encounters: 0, rounds: 0, monsters: [] },
      items: { gm_grants: [], trades: [], stash: [] }, lore: [], highlights: [],
    })
    campaignGet.mockResolvedValue({ id: 5, is_gm: false })
    renderPage()
    await screen.findByText(/campaign\.recap\.evening/)
    expect(screen.queryByText('campaign.recap.combat')).toBeNull()
    expect(screen.queryByText('campaign.recap.items')).toBeNull()
    expect(screen.queryByText('campaign.recap.lore')).toBeNull()
    expect(screen.queryByText('campaign.recap.highlights')).toBeNull()
  })

  it('GM can share to the group', async () => {
    recap.mockResolvedValue(RECAP)
    campaignGet.mockResolvedValue({ id: 5, is_gm: true })
    shareRecap.mockResolvedValue({ prepared_message_id: 'pm1' })
    shareTelegramMessage.mockResolvedValue(true)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.recap.share' }))
    expect(shareRecap).toHaveBeenCalledWith(8)
    expect(shareTelegramMessage).toHaveBeenCalledWith('pm1')
  })

  it('renders places block', async () => {
    recap.mockResolvedValue({ ...RECAP, places: [{ map_id: 4, marker_id: 12, title: 'Porto Grigio' }, { map_id: 5, marker_id: null, title: 'Costa Nord' }] })
    campaignGet.mockResolvedValue({ id: 5, is_gm: false })
    renderPage()
    expect(await screen.findByText('campaign.recap.places')).toBeInTheDocument()
    expect(screen.getByText('Porto Grigio')).toBeInTheDocument()
    expect(screen.getByText('Costa Nord')).toBeInTheDocument()
  })

  it('old recap without places renders without crash', async () => {
    recap.mockResolvedValue(RECAP)
    campaignGet.mockResolvedValue({ id: 5, is_gm: false })
    renderPage()
    await screen.findByText(/campaign\.recap\.evening/)
    expect(screen.queryByText('campaign.recap.places')).toBeNull()
  })

  it('shows the empty state on 404', async () => {
    recap.mockRejectedValue(new ApiError(404, 'recap_not_found'))
    campaignGet.mockResolvedValue({ id: 5, is_gm: false })
    renderPage()
    expect(await screen.findByText('campaign.recap.unavailable')).toBeInTheDocument()
  })
})
