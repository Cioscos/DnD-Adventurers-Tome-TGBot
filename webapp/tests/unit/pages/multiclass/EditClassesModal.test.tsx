import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import EditClassesModal from '@/pages/multiclass/EditClassesModal'
import type { CharacterFull } from '@/types'

const { distribute, update, add } = vi.hoisted(() => ({ distribute: vi.fn(), update: vi.fn(), add: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { classes: { distribute, update, add } }, ApiError: class ApiError extends Error {} }))
vi.mock('@/components/ui/SelectSheet', async () => {
  const React = await import('react')
  return { default: (p: { value: string; onChange: (v: string) => void }) =>
    React.createElement('button', { onClick: () => p.onChange('wizard') }, 'pick-wizard') }
})
vi.mock('@/components/ClassSkillChoice', () => ({ default: () => null }))
vi.mock('@/pages/multiclass/SubclassSelect', async () => {
  const React = await import('react')
  return { default: (p: { value: string; onChange: (v: string) => void }) =>
    React.createElement('input', { 'aria-label': 'subclass', value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }) }
})
vi.mock('@/hooks/useClassProficiencies', () => ({ useClassProficiencies: () => ({ data: null, isLoading: false }) }))
vi.mock('@/hooks/useDeferredBlur', () => ({ useDeferredBlur: () => ({ blurStyle: {}, onEntranceComplete: () => {} }) }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout', 'onAnimationComplete'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }), AnimatePresence: (p: { children?: unknown }) => p.children }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const char = {
  id: 7, rules_edition: '2014', abilities: [], ability_scores: [],
  classes: [{ id: 1, class_name: 'fighter', level: 3, subclass: null }, { id: 2, class_name: 'rogue', level: 1, subclass: null }],
} as unknown as CharacterFull

describe('EditClassesModal (punto 44)', () => {
  beforeEach(() => { distribute.mockReset(); add.mockReset(); update.mockReset() })
  it('sends the subclass together with the levels in one call, never a separate update', async () => {
    distribute.mockResolvedValue({ ...char, abilities: [] })
    renderWithProviders(<EditClassesModal char={char} targetLevel={4} onClose={vi.fn()} />)
    const [fighterSub] = screen.getAllByLabelText('subclass')
    fireEvent.change(fighterSub, { target: { value: 'Champion' } })
    await userEvent.click(screen.getByRole('button', { name: /character\.multiclass\.edit\.confirm/ }))
    await waitFor(() => expect(distribute).toHaveBeenCalledTimes(1))
    expect(distribute).toHaveBeenCalledWith(7, [{ class_id: 1, level: 3, subclass: 'Champion' }, { class_id: 2, level: 1 }])
    expect(update).not.toHaveBeenCalled()
  })

  it('Giro 1: a new class goes in the same distribute call; retrying after an error never calls classes.add', async () => {
    distribute.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce({ ...char, abilities: [] })
    renderWithProviders(<EditClassesModal char={char} targetLevel={5} milestone onClose={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /character\.multiclass\.add_class/ }))
    await userEvent.click(screen.getByText('pick-wizard'))
    await userEvent.click(screen.getByRole('button', { name: /common\.add/ }))
    const confirm = screen.getByRole('button', { name: /character\.multiclass\.edit\.confirm/ })
    await userEvent.click(confirm)
    await waitFor(() => expect(distribute).toHaveBeenCalledTimes(1))
    await userEvent.click(screen.getByRole('button', { name: /character\.multiclass\.edit\.confirm/ }))
    await waitFor(() => expect(distribute).toHaveBeenCalledTimes(2))
    for (const call of distribute.mock.calls) {
      expect(call[1][2]).toMatchObject({ new_class: { class_name: 'dnd.classes.wizard', level: 1 }, level: 1 })
    }
    expect(add).not.toHaveBeenCalled()
  })
})
