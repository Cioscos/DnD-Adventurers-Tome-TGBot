import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ClassOptionGroups from '@/pages/multiclass/ClassOptionGroups'
import type { CharacterClass, CharacterFull } from '@/types'

const { classOptions, replaceOption } = vi.hoisted(() => ({ classOptions: vi.fn(), replaceOption: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { choices: { classOptions, replaceOption } } }))
vi.mock('@/auth/telegram', () => ({ haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} } }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { defaultValue?: string }) => (o?.defaultValue ?? k), i18n: { language: 'it' } }) }
})

const entry = (key: string, name: string) => ({ key, name: { it: name, en: name }, summary: { it: '', en: '' } })
const char = { id: 7 } as unknown as CharacterFull
const fighter = { id: 11, class_name: 'Guerriero', level: 7, options: { maneuvers: ['trip', 'rally'], fighting_style: ['dueling'] } } as unknown as CharacterClass

beforeEach(() => {
  classOptions.mockReset().mockImplementation(async (_c: number, _k: number, group: string) => ({
    replaceable: group === 'maneuvers',
    chosen: group === 'maneuvers' ? [entry('trip', 'Attacco Sbilanciante'), entry('rally', 'Incoraggiamento')] : [entry('dueling', 'Duellare')],
    available: [entry('parry', 'Parata')],
  }))
  replaceOption.mockReset().mockResolvedValue({ id: 7 })
})

describe('ClassOptionGroups (R20: sostituire un\'opzione scelta dalla pagina della classe)', () => {
  it('shows only the groups the catalog says can be replaced, with the options chosen', async () => {
    renderWithProviders(<ClassOptionGroups char={char} cls={fighter} />)
    expect(await screen.findByTestId('option-group-maneuvers')).toHaveTextContent('Attacco Sbilanciante, Incoraggiamento')
    await waitFor(() => expect(classOptions).toHaveBeenCalledWith(7, 11, 'fighting_style'))
    expect(screen.queryByTestId('option-group-fighting_style')).not.toBeInTheDocument()  // lo stile non si cambia
  })

  it('replaces an option through the generic sheet', async () => {
    renderWithProviders(<ClassOptionGroups char={char} cls={fighter} />)
    await userEvent.click(await screen.findByText('character.level_choice.replace_title'))
    await userEvent.click(await screen.findByText('Attacco Sbilanciante'))
    await userEvent.click(screen.getByText('Parata'))
    await userEvent.click(screen.getByText('character.level_choice.confirm'))
    await waitFor(() => expect(replaceOption).toHaveBeenCalledWith(7, 11, { group: 'maneuvers', old_key: 'trip', new_key: 'parry' }))
  })

  it('shows nothing for a class without chosen options or for a group the catalog does not know', async () => {
    classOptions.mockRejectedValue(new Error('404'))
    const { container } = renderWithProviders(<ClassOptionGroups char={char} cls={{ ...fighter, options: { vecchio: ['x'] } } as CharacterClass} />)
    await waitFor(() => expect(classOptions).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
    const none = renderWithProviders(<ClassOptionGroups char={char} cls={{ ...fighter, options: undefined } as CharacterClass} />)
    expect(none.container).toBeEmptyDOMElement()
  })
})
