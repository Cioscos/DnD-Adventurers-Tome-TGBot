import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CharacterSelect from '@/pages/CharacterSelect'
import { speciesChoicesMissing, type Species2024Entry } from '@/lib/species'
import species2024 from '@/data/srd/species-2024.json'

const { list, me, create } = vi.hoisted(() => ({ list: vi.fn(), me: vi.fn(), create: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { characters: { list, create }, sessions: { me } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => vi.fn() }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), telegramConfirm: vi.fn() }))
vi.mock('@/components/ui/HPGauge', () => ({ default: () => null }))
vi.mock('@/pages/creation/AbilityScoresStep', () => ({ default: () => null }))
// Il foglio del wizard e quello del catalogo: contenuto in linea quando aperti.
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

afterEach(() => { list.mockReset(); me.mockReset(); create.mockReset() })

const elf = (species2024 as unknown as Species2024Entry[]).find((e) => e.key === '2024_elf')!
const user = userEvent.setup()
const next = () => user.click(screen.getByRole('button', { name: 'common.next →' }))

async function toSpecies(edition: '2014' | '2024', background?: string) {
  list.mockResolvedValue([])
  me.mockResolvedValue(null)
  renderWithProviders(<CharacterSelect />)
  await user.click(await screen.findByRole('button', { name: /character.select.new/ }))
  await user.type(screen.getByPlaceholderText('character.create.name_placeholder'), 'Lia')
  if (edition === '2024') await user.click(screen.getByRole('button', { name: 'character.settings.rules_edition.2024' }))
  await next()
  if (edition === '2014') {
    await next() // background 2014, facoltativo
    await user.click(screen.getByRole('button', { name: /character.create.skip_class/ }))
  }
  if (background) {
    await user.click(screen.getByRole('button', { name: /character.create.background_pick/ }))
    await user.click(await screen.findByText(background))
    expect(screen.queryByText('character.feats.origin_hint')).toBeNull()
  } else if (edition === '2024') await next() // senza background: passo del talento d'Origine
  await next()
  await user.click(screen.getByRole('button', { name: /character.create.species_pick/ }))
}

describe('creazione 2024: specie', () => {
  it('le scelte obbligatorie mancanti sono elencate', () => {
    expect(speciesChoicesMissing(elf, {})).toEqual(['lineage', 'spell_ability', 'skill'])
    expect(speciesChoicesMissing(elf, { lineage: 'drow', spell_ability: 'wisdom', skill: 'nope' })).toEqual(['skill'])
    expect(speciesChoicesMissing(elf, { lineage: 'drow', spell_ability: 'wisdom', skill: 'perception' })).toEqual([])
  })

  it('2024: catalogo species-2024, «Avanti» bloccato senza scelte, payload con species_2024 e background_2024', async () => {
    create.mockResolvedValue({ id: 9 })
    await toSpecies('2024', 'Accolito')
    expect(await screen.findByText('Goliath')).toBeTruthy()
    await user.click(screen.getByText('Elfo'))
    expect(screen.getByRole('button', { name: 'common.next →' })).toHaveProperty('disabled', true)

    await user.click(within(screen.getByRole('group', { name: 'Stirpe elfica' })).getByRole('button', { name: 'Drow' }))
    await user.click(within(screen.getByRole('group', { name: 'Caratteristica da incantatore' })).getByRole('button', { name: 'Saggezza' }))
    expect(screen.getByRole('button', { name: 'common.next →' })).toHaveProperty('disabled', true)
    await user.click(screen.getByRole('button', { name: 'Percezione' }))
    await next()

    await user.click(screen.getByRole('button', { name: /character.create.skip_class/ }))
    await next()
    await next() // punteggi
    await user.click(screen.getByRole('button', { name: 'character.create.create_cta' }))

    const extras = create.mock.calls[0][3]
    expect(extras.species_2024).toEqual({ key: '2024_elf', options: { lineage: 'drow', spell_ability: 'wisdom', skill: 'perception' } })
    expect(extras.background_2024).toEqual({
      key: 'acolyte', increases: { intelligence: 1, wisdom: 1, charisma: 1 }, equipment: 'pack',
    })
    expect(extras.rules_edition).toBe('2024')
    expect(extras).not.toHaveProperty('species')
    expect(extras).not.toHaveProperty('origin_feat')
  })

  it('Percezione già data dal background scelto: non è più sceglibile per la specie', async () => {
    await toSpecies('2024', 'Marinaio')  // acrobatics, perception
    await user.click(await screen.findByText('Elfo'))
    expect(screen.getByRole('button', { name: 'Percezione' })).toHaveProperty('disabled', true)
    await user.click(within(screen.getByRole('group', { name: 'Stirpe elfica' })).getByRole('button', { name: 'Drow' }))
    await user.click(within(screen.getByRole('group', { name: 'Caratteristica da incantatore' })).getByRole('button', { name: 'Saggezza' }))
    await user.click(screen.getByRole('button', { name: 'Intuizione' }))
    expect(screen.getByRole('button', { name: 'common.next →' })).toHaveProperty('disabled', false)
    // cambiando background con uno che dà Intuizione, la scelta della specie cade e va rifatta
    await user.click(screen.getByRole('button', { name: 'common.back' }))
    await user.click(screen.getByRole('button', { name: /Marinaio/ }))
    await user.click(await screen.findByText('Accolito'))
    await next()
    expect(screen.getByRole('button', { name: 'Intuizione' })).toHaveProperty('disabled', true)
    expect(screen.getByRole('button', { name: 'common.next →' })).toHaveProperty('disabled', true)
  })

  it('il background scelto nel 2014 non passa al 2024, e nell’identità 2024 non c’è il catalogo', async () => {
    create.mockResolvedValue({ id: 9 })
    list.mockResolvedValue([])
    me.mockResolvedValue(null)
    renderWithProviders(<CharacterSelect />)
    await user.click(await screen.findByRole('button', { name: /character.select.new/ }))
    await user.type(screen.getByPlaceholderText('character.create.name_placeholder'), 'Lia')
    await next()
    await user.click(screen.getByRole('button', { name: /character.create.background_pick/ }))
    await user.click(await screen.findByText('Accolito'))  // catalogo 2014: Intuizione, Religione
    await user.click(screen.getByRole('button', { name: 'common.back' }))
    await user.click(screen.getByRole('button', { name: 'character.settings.rules_edition.2024' }))
    for (let i = 0; i < 4; i++) await next() // nome, background, talento, specie
    await user.click(screen.getByRole('button', { name: /character.create.skip_class/ }))
    await next()
    await user.click(screen.getByRole('button', { name: 'character.create.scores_skip' }))
    expect(screen.queryByRole('button', { name: /character.create.background_pick/ })).toBeNull()
    expect(screen.getByPlaceholderText('character.identity.placeholder_background')).toHaveValue('')
    await user.click(screen.getByRole('button', { name: 'character.create.create_cta' }))
    expect(create.mock.calls[0][3]).not.toHaveProperty('skills')
    expect(create.mock.calls[0][2]).toBeNull()
  })

  it('2014: il passo specie apre il vecchio catalogo races', async () => {
    await toSpecies('2014')
    expect(await screen.findByText('Mezzorco')).toBeTruthy()
    expect(screen.queryByText('Goliath')).toBeNull()
  })
})
