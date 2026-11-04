import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Identity from '@/pages/Identity'

const { getChar, updateChar, layoutProps } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateChar: vi.fn(),
  layoutProps: { current: {} as { leaveGuard?: (proceed: () => void) => void } },
}))

vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, update: updateChar }, share: { card: vi.fn() } },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '3' }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return {
    default: (p: { children?: unknown; bottomAction?: unknown; leaveGuard?: (proceed: () => void) => void }) => {
      layoutProps.current = p
      return React.createElement('div', null, p.children, p.bottomAction)
    },
  }
})
vi.mock('@/hooks/useShareMessage', () => ({ useShareMessage: () => vi.fn() }))

const char = {
  id: 3, name: 'Eroe', speed: 30, languages: [], general_proficiencies: [],
  personality: {}, damage_modifiers: {},
  settings: { quick_actions: ['a'], senses: [{ type: 'darkvision', range_ft: 60 }] },
}

const saveButton = () => screen.findByRole('button', { name: /Salva modifiche|Save changes/i })
const typeIn = async (labelText: RegExp, text: string) => {
  const label = await screen.findByText(labelText)
  const input = label.closest('div')!.querySelector('input')!
  await userEvent.clear(input)
  if (text) await userEvent.type(input, text)
  return input
}

afterEach(() => {
  localStorage.clear()
  updateChar.mockReset()
  getChar.mockReset()
})

describe('Identity senses editor', () => {
  it('saves senses merged into the existing settings', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await screen.findByRole('switch', { name: /Vista pura|Truesight/i }))
    await userEvent.click(await saveButton())
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    const settings = updateChar.mock.calls[0][1].settings
    expect(settings.quick_actions).toEqual(['a'])
    expect(settings.senses).toEqual([
      { type: 'darkvision', range_ft: 60 },
      { type: 'truesight', range_ft: 60 },
    ])
  })
})

describe('Identity other speeds editor', () => {
  it('adds a fly speed next to senses and keeps the other settings', async () => {
    getChar.mockResolvedValue({ ...char, settings: { ...char.settings, speeds: [{ type: 'swim', range_ft: 30 }] } })
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await screen.findByRole('switch', { name: /^(Volare|Fly)$/i }))
    await userEvent.click(await saveButton())
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    const settings = updateChar.mock.calls[0][1].settings
    expect(settings.senses).toEqual([{ type: 'darkvision', range_ft: 60 }])
    expect(settings.speeds).toEqual([
      { type: 'fly', range_ft: 30 },
      { type: 'swim', range_ft: 30 },
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
    await userEvent.click(screen.getByRole('button', { name: /^(Aspetto|Appearance)$/ }))
    await typeIn(/^(Età|Age)$/, '27')
    await userEvent.click(await saveButton())
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    const body = updateChar.mock.calls.at(-1)![1]
    expect(body.general_proficiencies).toEqual({ armor: [], weapons: [], tools: [], other: ['Liuto'] })
    expect(body.personality).toMatchObject({ traits: 'T', ideals: 'I', extra: 'keep', age: '27' })
  })

  it('opens Appearance by itself when it already has content', async () => {
    getChar.mockResolvedValue({ ...char, personality: { age: '40' } })
    renderWithProviders(<Identity />)
    expect(await screen.findByDisplayValue('40')).toBeInTheDocument()
  })
})

describe('Identity damage modifiers', () => {
  const save = async () => {
    await userEvent.click(await saveButton())
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    return updateChar.mock.calls.at(-1)![1].damage_modifiers
  }
  const dmgButton = (name: RegExp) => screen.findByRole('button', { name })

  it('keeps a type in one list only: choosing another moves it, the dash clears it', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await dmgButton(/^(Fuoco|Fire): (Resistenze|Resistances)$/))
    await userEvent.click(await dmgButton(/^(Fuoco|Fire): (Immunità|Immunities)$/))
    await userEvent.click(await dmgButton(/^(Freddo|Cold): (Vulnerabilità|Vulnerabilities)$/))
    await userEvent.click(await dmgButton(/^(Freddo|Cold): (normale|normal)$/))
    await userEvent.click(await dmgButton(/^(Veleno|Poison): (Resistenze|Resistances)$/))
    expect(await save()).toEqual({ resistances: ['poison'], immunities: ['fire'], vulnerabilities: [] })
  })

  it('summarises what is active above the rows', async () => {
    getChar.mockResolvedValue({ ...char, damage_modifiers: { resistances: ['fire'] } })
    renderWithProviders(<Identity />)
    expect(await screen.findByText(/^(Resistenze|Resistances):/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^(Fuoco|Fire): (Resistenze|Resistances)$/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps legacy free text as a removable custom chip and adds new custom entries', async () => {
    const legacy = { ...char, damage_modifiers: { resistances: ['Danni non magici'] } }
    getChar.mockResolvedValue(legacy)
    updateChar.mockResolvedValue(legacy)
    renderWithProviders(<Identity />)
    // Con un tipo personalizzato il gruppo parte aperto.
    const chip = await screen.findByRole('button', { name: /Danni non magici/ })
    expect(screen.getAllByText(/non applicat|not applied/i).length).toBeGreaterThan(0)
    const resInput = chip.closest('div')!.querySelector('input')!
    await userEvent.type(resInput, 'Argento{Enter}')
    await userEvent.click(screen.getByRole('button', { name: /Danni non magici/ }))
    const mods = await save()
    expect(mods.resistances).toEqual(['Argento'])
  })

  it('normalizes a typed canonical alias to its damage type key', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await screen.findByRole('button', { name: /personalizzati|Custom types/i }))
    const inputs = await screen.findAllByPlaceholderText(/personalizzat|custom/i)
    await userEvent.type(inputs[1], 'Fire{Enter}')
    await userEvent.type(inputs[0], 'fuoco{Enter}')  // moves it from immunities to resistances
    const mods = await save()
    expect(mods.resistances).toEqual(['fire'])
    expect(mods.immunities).toEqual([])
  })
})

describe('Identity validation', () => {
  it('blocks a blank name and does not call the API', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await typeIn(/^(Nome|Name)$/, '')
    await userEvent.click(await saveButton())
    expect(await screen.findByText(/bisogno di un nome|needs a name/i)).toBeInTheDocument()
    expect(updateChar).not.toHaveBeenCalled()
  })

  it('blocks a negative speed and clears the error once corrected', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    const speed = await typeIn(/^(Velocità|Speed)$/, '-5')
    await userEvent.click(await saveButton())
    expect(await screen.findByText(/numero da 0|number from 0/i)).toBeInTheDocument()
    expect(updateChar).not.toHaveBeenCalled()
    await userEvent.clear(speed)
    await userEvent.type(speed, '25')
    expect(screen.queryByText(/numero da 0|number from 0/i)).not.toBeInTheDocument()
    await userEvent.click(await saveButton())
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
  })

  it('saves a speed of 0 as 0 instead of falling back to 30', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await typeIn(/^(Velocità|Speed)$/, '0')
    await userEvent.click(await saveButton())
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    expect(updateChar.mock.calls[0][1].speed).toBe(0)
  })
})

describe('Identity unsaved changes', () => {
  it('shows Save only when something changed, and guards leaving only then', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await screen.findByRole('switch', { name: /Vista pura|Truesight/i })
    expect(screen.queryByRole('button', { name: /Salva modifiche|Save changes/i })).not.toBeInTheDocument()
    expect(layoutProps.current.leaveGuard).toBeUndefined()
    await userEvent.click(screen.getByRole('switch', { name: /Vista pura|Truesight/i }))
    expect(await saveButton()).toBeInTheDocument()
    expect(layoutProps.current.leaveGuard).toBeTypeOf('function')
  })

  const openLeaveSheet = async () => {
    await userEvent.click(await screen.findByRole('switch', { name: /Vista pura|Truesight/i }))
    const proceed = vi.fn()
    act(() => layoutProps.current.leaveGuard!(proceed))
    return proceed
  }

  it('leaving without saving drops the local draft and proceeds', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    const proceed = await openLeaveSheet()
    fireEvent.click(await screen.findByRole('button', { name: /Esci senza salvare|Leave without saving/i }))
    expect(proceed).toHaveBeenCalledOnce()
    expect(updateChar).not.toHaveBeenCalled()
    expect(localStorage.getItem('identity-draft-3')).toBeNull()
  })

  it('save and leave proceeds only after the save succeeds', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    const proceed = await openLeaveSheet()
    fireEvent.click(await screen.findByRole('button', { name: /Salva ed esci|Save and leave/i }))
    await waitFor(() => expect(proceed).toHaveBeenCalledOnce())
    expect(updateChar).toHaveBeenCalledOnce()
  })

  it('save and leave stays on the page when the save fails', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockRejectedValue(new Error('network'))
    renderWithProviders(<Identity />)
    const proceed = await openLeaveSheet()
    fireEvent.click(await screen.findByRole('button', { name: /Salva ed esci|Save and leave/i }))
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    expect(proceed).not.toHaveBeenCalled()
    expect(localStorage.getItem('identity-draft-3')).not.toBeNull()
  })

  it('restores a draft left behind by an interruption, and can discard it', async () => {
    getChar.mockResolvedValue(char)
    const first = renderWithProviders(<Identity />)
    await typeIn(/^(Nome|Name)$/, 'Bozza')
    await waitFor(() => expect(localStorage.getItem('identity-draft-3')).toContain('Bozza'))
    first.unmount()

    renderWithProviders(<Identity />)
    expect(await screen.findByDisplayValue('Bozza')).toBeInTheDocument()
    expect(await saveButton()).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /^(Scarta|Discard)$/ }))
    expect(await screen.findByDisplayValue('Eroe')).toBeInTheDocument()
    await waitFor(() => expect(localStorage.getItem('identity-draft-3')).toBeNull())
  })

  it('removes the draft after a successful save', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await screen.findByRole('switch', { name: /Vista pura|Truesight/i }))
    await waitFor(() => expect(localStorage.getItem('identity-draft-3')).not.toBeNull())
    await userEvent.click(await saveButton())
    await waitFor(() => expect(localStorage.getItem('identity-draft-3')).toBeNull())
  })
})
