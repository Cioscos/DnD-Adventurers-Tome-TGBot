import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Identity from '@/pages/Identity'

const { getChar, updateChar } = vi.hoisted(() => ({ getChar: vi.fn(), updateChar: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, update: updateChar }, share: { card: vi.fn() } },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '3' }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/hooks/useShareMessage', () => ({ useShareMessage: () => vi.fn() }))

const char = {
  id: 3, name: 'Eroe', speed: 30, languages: [], general_proficiencies: [],
  personality: {}, damage_modifiers: {},
  settings: { quick_actions: ['a'], senses: [{ type: 'darkvision', range_ft: 60 }] },
}

describe('Identity senses editor', () => {
  it('saves senses merged into the existing settings', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await screen.findByRole('button', { name: /Vista pura|Truesight/i }))
    await userEvent.click(await screen.findByRole('button', { name: /Salva ora|Save now/i }))
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    const settings = updateChar.mock.calls[0][1].settings
    expect(settings.quick_actions).toEqual(['a'])
    expect(settings.senses).toEqual([
      { type: 'darkvision', range_ft: 60 },
      { type: 'truesight', range_ft: 60 },
    ])
  })
})

describe('Identity proficiencies and appearance', () => {
  it('reads a legacy list into "other" and saves categories + appearance keeping personality', async () => {
    const legacy = { ...char, general_proficiencies: ['Liuto'], personality: { traits: 'T', ideals: 'I', extra: 'keep' } }
    getChar.mockResolvedValue(legacy)
    updateChar.mockResolvedValue(legacy)
    renderWithProviders(<Identity />)
    expect(await screen.findByText('Liuto')).toBeInTheDocument()
    const label = await screen.findByText(/^(Età|Age)$/)
    await userEvent.type(label.closest('div')!.querySelector('input')!, '27')
    await userEvent.click(await screen.findByRole('button', { name: /Salva ora|Save now/i }))
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    const body = updateChar.mock.calls.at(-1)![1]
    expect(body.general_proficiencies).toEqual({ armor: [], weapons: [], tools: [], other: ['Liuto'] })
    expect(body.personality).toMatchObject({ traits: 'T', ideals: 'I', extra: 'keep', age: '27' })
  })
})

describe('Identity custom damage modifiers', () => {
  const save = async () => {
    await userEvent.click(await screen.findByRole('button', { name: /Salva ora|Save now/i }))
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    return updateChar.mock.calls.at(-1)![1].damage_modifiers
  }

  it('keeps legacy free text as a removable custom chip and adds new custom entries', async () => {
    updateChar.mockReset()
    const legacy = { ...char, damage_modifiers: { resistances: ['Danni non magici'] } }
    getChar.mockResolvedValue(legacy)
    updateChar.mockResolvedValue(legacy)
    renderWithProviders(<Identity />)
    expect(await screen.findByText('Danni non magici')).toBeInTheDocument()
    expect(screen.getAllByText(/non applicat|not applied/i).length).toBeGreaterThan(0)
    const resInput = screen.getByText('Danni non magici').closest('div')!.querySelector('input')!
    await userEvent.type(resInput, 'Argento{Enter}')
    await userEvent.click(screen.getByRole('button', { name: /Danni non magici/ }))
    const mods = await save()
    expect(mods.resistances).toEqual(['Argento'])
  })

  it('normalizes a typed canonical alias to its damage type key', async () => {
    updateChar.mockReset()
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    const inputs = await screen.findAllByPlaceholderText(/personalizzat|custom/i)
    await userEvent.type(inputs[1], 'Fire{Enter}')
    await userEvent.type(inputs[0], 'fuoco{Enter}')  // moves it from immunities to resistances
    const mods = await save()
    expect(mods.resistances).toEqual(['fire'])
    expect(mods.immunities).toEqual([])
  })
})
