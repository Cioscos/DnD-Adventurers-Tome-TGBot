import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import HpQuickSheet from '@/components/character/HpQuickSheet'
import { ApiError } from '@/api/client'
import type { CharacterFull } from '@/types'

const { updateHpSpy, undoHpSpy, showUndoToastSpy, toastError, notifySpy } = vi.hoisted(() => ({
  updateHpSpy: vi.fn(),
  undoHpSpy: vi.fn(),
  showUndoToastSpy: vi.fn(),
  toastError: vi.fn(),
  notifySpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { characters: { updateHp: updateHpSpy, undoHp: undoHpSpy } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) {
      super(`API ${status}`)
    }
  },
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/UndoToast', () => ({ showUndoToast: showUndoToastSpy }))
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ error: toastError, warning: vi.fn(), success: vi.fn() }),
}))
vi.mock('@/lib/mutationError', () => ({ notifyMutationError: notifySpy }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

const char = { id: 42, current_hit_points: 10, hit_points: 20 } as CharacterFull

afterEach(() => {
  updateHpSpy.mockReset()
  undoHpSpy.mockReset()
  showUndoToastSpy.mockReset()
  toastError.mockReset()
  notifySpy.mockReset()
})

async function applyDamage() {
  renderWithProviders(<HpQuickSheet char={char} open onClose={() => {}} />)
  await userEvent.type(screen.getByPlaceholderText('0'), '4')
  await userEvent.click(screen.getByRole('button', { name: 'character.hp.quick_apply' }))
  await waitFor(() => expect(updateHpSpy).toHaveBeenCalled())
}

describe('HpQuickSheet undo', () => {
  it('undo calls undoHp with the op id', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    undoHpSpy.mockResolvedValue(char)
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(undoHpSpy).toHaveBeenCalledWith(42, 'abc'))
    expect(updateHpSpy).toHaveBeenCalledTimes(1)
  })

  it('shows stale message on 409', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    undoHpSpy.mockRejectedValue(new ApiError(409, 'x'))
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.hp.undo_stale'))
    expect(notifySpy).not.toHaveBeenCalled()
  })

  it('shows network message when undo fails without a response', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc' })
    undoHpSpy.mockRejectedValue(new TypeError('Failed to fetch'))
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    showUndoToastSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(notifySpy).toHaveBeenCalled())
    expect(toastError).not.toHaveBeenCalledWith('character.hp.undo_stale')
  })

  it('no undo toast without hp_undo_id', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: null })
    await applyDamage()
    await waitFor(() => expect(updateHpSpy).toHaveBeenCalled())
    expect(showUndoToastSpy).not.toHaveBeenCalled()
  })

  it('undo toast mentions homebrew effects', async () => {
    updateHpSpy.mockResolvedValue({ ...char, hp_undo_id: 'abc', homebrew_notifications: [{ a: 1 }] })
    await applyDamage()
    await waitFor(() => expect(showUndoToastSpy).toHaveBeenCalled())
    expect(showUndoToastSpy.mock.calls[0][0].message).toContain('character.hp.undo_homebrew_note')
  })
})
