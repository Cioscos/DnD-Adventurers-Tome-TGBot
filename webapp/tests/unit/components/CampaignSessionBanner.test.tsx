import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import CampaignSessionBanner from '@/components/ui/CampaignSessionBanner'

const m = vi.hoisted(() => ({ list: vi.fn(), activeForMe: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { campaigns: m } }))
vi.mock('@/pages/campaign/JoinCampaignSessionSheet', () => ({ default: () => null }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

afterEach(() => Object.values(m).forEach((f) => f.mockReset()))

describe('CampaignSessionBanner', () => {
  it('does not poll active-for-me when the user has no campaigns', async () => {
    m.list.mockResolvedValue([])
    renderWithProviders(<CampaignSessionBanner />)
    await waitFor(() => expect(m.list).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 30))
    expect(m.activeForMe).not.toHaveBeenCalled()
  })

  it('shows the open session of a campaign the user belongs to', async () => {
    m.list.mockResolvedValue([{ id: 3, name: 'Saga' }])
    m.activeForMe.mockResolvedValue([{ campaign_id: 3, campaign_name: 'Saga', session_id: 9, my_last_character_id: null }])
    renderWithProviders(<CampaignSessionBanner />)
    expect(await screen.findByText('Saga')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'campaign.enter' })).toBeInTheDocument()
  })
})
