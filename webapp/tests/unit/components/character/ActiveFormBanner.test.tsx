import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ActiveFormBanner from '@/components/character/ActiveFormBanner'
import type { ActiveForm } from '@/types'

const { deactivate, toastError, notifyMutationError } = vi.hoisted(() => ({
  deactivate: vi.fn(), toastError: vi.fn(), notifyMutationError: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { companions: { deactivate } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/lib/mutationError', () => ({ notifyMutationError }))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))

const form = { companion_id: 4, name: 'Lupo' } as unknown as ActiveForm

describe('ActiveFormBanner', () => {
  it('ends the form with the one tap', async () => {
    deactivate.mockResolvedValue({})
    renderWithProviders(<ActiveFormBanner charId={7} form={form} />)
    await userEvent.click(screen.getByText('character.extras.end_form'))
    await waitFor(() => expect(deactivate).toHaveBeenCalledWith(7, 4))
  })

  it('says that returning to the normal form needs the bonus action when it is already spent', async () => {
    const { ApiError } = await import('@/api/client')
    deactivate.mockRejectedValueOnce(new ApiError(409, { code: 'turn_slot_used' }))
    renderWithProviders(<ActiveFormBanner charId={7} form={form} />)
    await userEvent.click(screen.getByText('character.extras.end_form'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.extras.return_bonus_used'))
    expect(notifyMutationError).not.toHaveBeenCalled()
  })
})
