import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../../utils/renderWithProviders'
import EnrollSheet from '@/pages/campaign/EnrollSheet'

const { list, enroll, navigateSpy, toastError } = vi.hoisted(() => ({
  list: vi.fn(), enroll: vi.fn(), navigateSpy: vi.fn(), toastError: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { characters: { list }, campaigns: { enroll } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('e') }
  },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError }) }))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

afterEach(() => { list.mockReset(); enroll.mockReset(); navigateSpy.mockReset(); toastError.mockReset() })

const chars = [
  { id: 7, name: 'Lyra', class_summary: 'Ranger' },
  { id: 8, name: 'Fenn', class_summary: 'Rogue' },
]

describe('EnrollSheet', () => {
  it('invalidates the banner and campaigns queries on success', async () => {
    list.mockResolvedValue(chars)
    enroll.mockResolvedValue({ id: 5 })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const spy = vi.spyOn(client, 'invalidateQueries')
    renderWithProviders(<EnrollSheet open onClose={() => {}} code="AB12CD34" />, { client })
    await userEvent.click(await screen.findByText('Lyra'))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enroll_confirm' }))
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ['campaign-active-for-me'] }))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['campaigns'] })
  })

  it('with no characters explains and offers to create one', async () => {
    list.mockResolvedValue([])
    renderWithProviders(<EnrollSheet open onClose={() => {}} code="AB12CD34" />)
    expect(await screen.findByText('campaign.enroll_no_characters')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'campaign.enroll_confirm' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enroll_create' }))
    expect(navigateSpy).toHaveBeenCalledWith('/')
  })

  it('enrolls the picked character and opens the campaign page', async () => {
    list.mockResolvedValue(chars)
    enroll.mockResolvedValue({ id: 5 })
    renderWithProviders(<EnrollSheet open onClose={() => {}} code="AB12CD34" />)
    await userEvent.click(await screen.findByText('Fenn'))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enroll_confirm' }))
    await waitFor(() => expect(enroll).toHaveBeenCalledWith('AB12CD34', 8))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/campaign/5', { replace: true }))
  })

  it('keeps confirm disabled until a character is picked', async () => {
    list.mockResolvedValue(chars)
    renderWithProviders(<EnrollSheet open onClose={() => {}} code="AB12CD34" />)
    await screen.findByText('Lyra')
    expect(screen.getByRole('button', { name: 'campaign.enroll_confirm' })).toBeDisabled()
  })

  it.each([
    ['already_in_campaign', 'campaign.enroll_err_already'],
    ['gm_cannot_enroll', 'campaign.enroll_err_gm'],
    ['campaign_not_found', 'campaign.enroll_err_not_found'],
  ])('maps %s to its toast', async (detail, key) => {
    const { ApiError } = await import('@/api/client')
    list.mockResolvedValue([chars[0]])
    enroll.mockRejectedValue(new (ApiError as unknown as new (s: number, d: unknown) => Error)(409, detail))
    renderWithProviders(<EnrollSheet open onClose={() => {}} code="AB12CD34" />)
    await userEvent.click(await screen.findByText('Lyra'))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enroll_confirm' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(key))
    expect(navigateSpy).not.toHaveBeenCalled()
  })
})
