import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import WildHealSheet from '@/pages/extras/WildHealSheet'
import type { Companion } from '@/types'

const { wildHeal, toastInfo, toastError, notifyMutationError } = vi.hoisted(() => ({
  wildHeal: vi.fn(), toastInfo: vi.fn(), toastError: vi.fn(), notifyMutationError: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { companions: { wildHeal } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: toastInfo, error: toastError, success: vi.fn() }) }))
vi.mock('@/lib/mutationError', async (orig) => ({ ...(await orig<typeof import('@/lib/mutationError')>()), notifyMutationError }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})

const comp = { id: 4, name: 'Orso' } as unknown as Companion
const slots = [{ level: 1, left: 2 }, { level: 3, left: 1 }]

afterEach(() => vi.clearAllMocks())

describe('WildHealSheet (Combat Wild Shape)', () => {
  it('offers one button per slot level and sends only the level: the server rolls and applies', async () => {
    wildHeal.mockResolvedValue({ companion: comp, slot_level: 3, rolls: [4, 5, 6], healed: 15 })
    const onClose = vi.fn()
    renderWithProviders(<WildHealSheet charId={7} comp={comp} slots={slots} onClose={onClose} />)
    await userEvent.click(screen.getByText(/wild_heal_slot.*"level":3/))
    await waitFor(() => expect(wildHeal).toHaveBeenCalledWith(7, 4, 3))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith(expect.stringContaining('"n":15'), { description: '4 + 5 + 6' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('says when there is no slot left to spend', () => {
    renderWithProviders(<WildHealSheet charId={7} comp={comp} slots={[]} onClose={() => {}} />)
    expect(screen.getByText('character.extras.wild_heal_no_slot')).toBeInTheDocument()
  })

  it('explains a spent bonus action and a slot that is gone, without the technical message', async () => {
    const { ApiError } = await import('@/api/client')
    wildHeal.mockRejectedValueOnce(new ApiError(409, { code: 'turn_slot_used' }))
    renderWithProviders(<WildHealSheet charId={7} comp={comp} slots={slots} onClose={() => {}} />)
    await userEvent.click(screen.getByText(/wild_heal_slot.*"level":1/))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.attack.bonus_used'))
    wildHeal.mockRejectedValueOnce(new ApiError(409, { code: 'no_slot' }))
    await userEvent.click(screen.getByText(/wild_heal_slot.*"level":1/))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.extras.wild_heal_no_slot'))
    expect(notifyMutationError).not.toHaveBeenCalled()
  })

  it('says the form is already at full hit points, without the technical message', async () => {
    const { ApiError } = await import('@/api/client')
    wildHeal.mockRejectedValueOnce(new ApiError(409, { code: 'form_full_hp' }))
    renderWithProviders(<WildHealSheet charId={7} comp={comp} slots={slots} onClose={() => {}} />)
    await userEvent.click(screen.getByText(/wild_heal_slot.*"level":1/))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.extras.wild_heal_full'))
    expect(notifyMutationError).not.toHaveBeenCalled()
  })
})
