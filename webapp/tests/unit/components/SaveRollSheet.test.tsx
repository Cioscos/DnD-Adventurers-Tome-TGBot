import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SaveRollSheet from '@/components/SaveRollSheet'

const { rollSpy, dismissSpy, toastError } = vi.hoisted(() => ({ rollSpy: vi.fn(), dismissSpy: vi.fn(), toastError: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { characters: { get: vi.fn(), pendingSaves: { roll: rollSpy, dismiss: dismissSpy } } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('api error') }
  },
}))
vi.mock('@/hooks/useD20Roll', () => ({
  useD20Roll: () => async () => undefined,
  d20Arg: (mode: string) => (mode === 'normal' ? undefined : { dice: undefined, mode }),
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError }) }))
vi.mock('@/components/ui/Sheet', () => ({ default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const save = { id: 1, slug: 'poisoned', ability: 'constitution', dc: 15, status: 'pending' as const, created_at: '' }
const result = (passed: boolean) => ({
  save: { ...save, status: passed ? 'passed' : 'failed' },
  roll: { die: 10, bonus: 2, total: passed ? 17 : 12, is_critical: false, is_fumble: false },
  passed,
  condition_removed: passed,
})

function setup(inspiration = false) {
  const qc = new QueryClient()
  qc.setQueryData(['character', 7], { heroic_inspiration: inspiration })
  const invalidate = vi.spyOn(qc, 'invalidateQueries')
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={qc}>
      <SaveRollSheet charId={7} saves={[save]} onClose={onClose} />
    </QueryClientProvider>,
  )
  return { onClose, invalidate }
}

function setupLive(saves: (typeof save)[], inspiration = false) {
  const qc = new QueryClient()
  qc.setQueryData(['character', 7], { heroic_inspiration: inspiration })
  const onClose = vi.fn()
  const ui = (list: (typeof save)[]) => (
    <QueryClientProvider client={qc}>
      <SaveRollSheet charId={7} saves={list} onClose={onClose} />
    </QueryClientProvider>
  )
  const view = render(ui(saves))
  return { onClose, shrink: () => view.rerender(ui([])) }
}

beforeEach(() => {
  rollSpy.mockReset()
  dismissSpy.mockReset()
  toastError.mockReset()
})

describe('SaveRollSheet', () => {
  it('Advantage sends mode advantage', async () => {
    rollSpy.mockResolvedValue(result(true))
    setup()
    await userEvent.click(screen.getByText('common.roll_mode.advantage'))
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    await waitFor(() => expect(rollSpy).toHaveBeenCalled())
    expect(rollSpy.mock.calls[0][2]).toEqual({ dice: undefined, mode: 'advantage' })
    expect(rollSpy.mock.calls[0][3]).toBe(false)
  })

  it('passed shows the freedom text', async () => {
    rollSpy.mockResolvedValue(result(true))
    setup()
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    expect(await screen.findByText('pendingSaves.passed')).toBeInTheDocument()
  })

  it('failed with inspiration offers the re-roll', async () => {
    rollSpy.mockResolvedValueOnce(result(false)).mockResolvedValueOnce(result(true))
    setup(true)
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    await userEvent.click(await screen.findByText('character.inspiration.use_reroll'))
    await waitFor(() => expect(rollSpy).toHaveBeenCalledTimes(2))
    expect(rollSpy.mock.calls[1][3]).toBe(true)
  })

  it('failed without inspiration has no re-roll', async () => {
    rollSpy.mockResolvedValue(result(false))
    setup(false)
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    await screen.findByText('pendingSaves.failed')
    expect(screen.queryByText('character.inspiration.use_reroll')).not.toBeInTheDocument()
  })

  it('409 condition_gone closes the sheet and invalidates', async () => {
    const { ApiError } = await import('@/api/client')
    rollSpy.mockRejectedValue(new ApiError(409, { code: 'condition_gone' }))
    const { onClose, invalidate } = setup()
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(toastError).toHaveBeenCalledWith('pendingSaves.gone')
    expect(invalidate).toHaveBeenCalled()
  })

  it('keeps the passed outcome when the live saves list empties', async () => {
    rollSpy.mockResolvedValue(result(true))
    const { onClose, shrink } = setupLive([save])
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    await screen.findByText('pendingSaves.passed')
    shrink()
    expect(screen.getByText('pendingSaves.passed')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('walks a two-save queue even if the live list shrinks', async () => {
    rollSpy.mockResolvedValue(result(true))
    const { onClose, shrink } = setupLive([save, { ...save, id: 2, ability: 'wisdom' }])
    await userEvent.click(screen.getByText('pendingSaves.roll'))
    await screen.findByText('pendingSaves.passed')
    shrink()
    await userEvent.click(screen.getByText('pendingSaves.ok'))
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByText('pendingSaves.roll')).toBeInTheDocument()
  })

  it('a failed save opens on its outcome with re-roll and OK dismisses', async () => {
    dismissSpy.mockResolvedValue(undefined)
    const failed = { ...save, status: 'failed' as const }
    const { onClose } = setupLive([failed], true)
    expect(screen.getByText('pendingSaves.failed')).toBeInTheDocument()
    expect(screen.getByText('character.inspiration.use_reroll')).toBeInTheDocument()
    await userEvent.click(screen.getByText('pendingSaves.ok'))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(dismissSpy).toHaveBeenCalledWith(7, 1)
  })
})
