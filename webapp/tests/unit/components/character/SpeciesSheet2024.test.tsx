import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import SpeciesSheet2024 from '@/components/character/SpeciesSheet2024'
import Identity from '@/pages/Identity'
import type { CharacterFull } from '@/types'

const { preview, apply, getChar } = vi.hoisted(() => ({ preview: vi.fn(), apply: vi.fn(), getChar: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { species: { preview, apply }, characters: { get: getChar, update: vi.fn() }, share: { card: vi.fn() } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super(String(detail)) }
  },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '3' }), useNavigate: () => vi.fn() }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), canShareMessage: () => false }))
vi.mock('@/hooks/useShareMessage', () => ({ useShareMessage: () => vi.fn() }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

afterEach(() => { preview.mockReset(); apply.mockReset(); getChar.mockReset(); localStorage.clear() })

const base = {
  id: 3, name: 'Eroe', speed: 30, race: 'Nano delle colline', languages: [], general_proficiencies: [],
  personality: {}, damage_modifiers: {}, settings: {}, abilities: [], skills: {},
}
const char24 = { ...base, rules_edition: '2024', species_key: null } as unknown as CharacterFull
const user = userEvent.setup()

describe('SpeciesSheet2024', () => {
  it('mostra i cambiamenti tradotti e non scrive finché non si conferma', async () => {
    preview.mockResolvedValue({ changes: [
      'speed_reset', 'traits_archived:2', 'trait_removed:Scurovisione', 'trait_removed:Robustezza nanica',
      'hp_check', 'scores_check', 'skill_added:perception', 'feat_added:2024_alert',
    ] })
    apply.mockResolvedValue({ ...char24, species_key: '2024_dwarf', abilities: [] })
    const onClose = vi.fn()
    renderWithProviders(<SpeciesSheet2024 char={char24} open onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: 'Scegli dal catalogo' }))
    await user.click(await screen.findByText('Nano'))
    await user.click(screen.getByRole('button', { name: 'Vedi i cambiamenti' }))

    expect(preview).toHaveBeenCalledWith(3, '2024_dwarf', {})
    expect(await screen.findByText(/La velocità torna/)).toBeTruthy()
    expect(screen.getByText(/2 tratti della vecchia razza verranno rimossi/)).toBeTruthy()
    expect(screen.getByText('Scurovisione')).toBeTruthy()
    expect(screen.getByText('Robustezza nanica')).toBeTruthy()
    expect(screen.getByText(/Competenza in Percezione/)).toBeTruthy()
    expect(screen.getByText(/Allerta/)).toBeTruthy()
    expect(screen.queryByText(/archiviat/i)).toBeNull()
    expect(apply).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Conferma' }))
    expect(apply).toHaveBeenCalledWith(3, '2024_dwarf', {})
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('le scelte già salvate si ripropongono senza le chiavi del server', async () => {
    preview.mockResolvedValue({ changes: [] })
    const elf = { ...char24, species_key: '2024_elf',
      species_options: { lineage: 'drow', spell_ability: 'wisdom', skill: 'perception', _granted_skill: 'perception' } } as unknown as CharacterFull
    renderWithProviders(<SpeciesSheet2024 char={elf} open onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Vedi i cambiamenti' }))
    expect(preview).toHaveBeenCalledWith(3, '2024_elf', { lineage: 'drow', spell_ability: 'wisdom', skill: 'perception' })
    expect(await screen.findByText('Nessun altro cambiamento sulla scheda.')).toBeTruthy()
  })

  it('abilità già competenti non sceglibili, tranne quella data dalla specie attuale', async () => {
    const elf = { ...char24, species_key: '2024_elf', skills: { perception: true, survival: 'expert' },
      species_options: { lineage: 'drow', spell_ability: 'wisdom', skill: 'perception', _granted_skill: 'perception' } } as unknown as CharacterFull
    renderWithProviders(<SpeciesSheet2024 char={elf} open onClose={vi.fn()} />)
    expect((await screen.findByRole('button', { name: 'Percezione' })).hasAttribute('disabled')).toBe(false)
    expect(screen.getByRole('button', { name: 'Sopravvivenza' }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByRole('button', { name: 'Intuizione' }).hasAttribute('disabled')).toBe(false)
  })

  it('un 422 mostra il suo testo', async () => {
    const { ApiError } = await import('@/api/client')
    preview.mockRejectedValue(new ApiError(422, 'species_options_invalid'))
    renderWithProviders(<SpeciesSheet2024 char={{ ...char24, species_key: '2024_dwarf' } as CharacterFull} open onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Vedi i cambiamenti' }))
    expect(await screen.findByText(/Le scelte della specie non sono valide/)).toBeTruthy()
  })

  it('Umano con un talento da completare: rimanda alla pagina Abilità', async () => {
    preview.mockResolvedValue({ changes: ['feat_added:2024_skilled'] })
    apply.mockResolvedValue({ ...char24, species_key: '2024_human', abilities: [
      { id: 7, name: 'Abile', feature_key: 'feat.2024_skilled', feat_status: 'incomplete' },
    ] })
    const human = { ...char24, species_key: '2024_human', species_options: { size: 'medium', skill: 'stealth', origin_feat: '2024_skilled' } } as unknown as CharacterFull
    const onClose = vi.fn()
    renderWithProviders(<SpeciesSheet2024 char={human} open onClose={onClose} />)
    await user.click(screen.getByRole('button', { name: 'Vedi i cambiamenti' }))
    await user.click(await screen.findByRole('button', { name: 'Conferma' }))
    expect(await screen.findByText(/completalo nella pagina Abilità/)).toBeTruthy()
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('Identity: pulsante della specie 2024', () => {
  it('c’è per un 2024 («Scegli specie 2024», poi «Cambia specie»)', async () => {
    getChar.mockResolvedValue(char24)
    renderWithProviders(<Identity />)
    expect(await screen.findByRole('button', { name: 'Scegli specie 2024' })).toBeTruthy()
  })

  it('dice «Cambia specie» se la specie c’è già', async () => {
    getChar.mockResolvedValue({ ...char24, species_key: '2024_dwarf' })
    renderWithProviders(<Identity />)
    expect(await screen.findByRole('button', { name: 'Cambia specie' })).toBeTruthy()
  })

  it('non c’è per un 2014', async () => {
    getChar.mockResolvedValue({ ...base, rules_edition: '2014' })
    renderWithProviders(<Identity />)
    await screen.findByText('Razza')
    expect(screen.queryByRole('button', { name: /specie/i })).toBeNull()
  })
})
